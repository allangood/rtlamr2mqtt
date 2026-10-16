import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from meter_reader import MeterReader


@pytest.fixture
def mock_rtlamr():
    proc = AsyncMock()
    proc.is_alive = True
    proc.start_with_retry = AsyncMock(return_value=True)
    proc.stop = AsyncMock()
    return proc


@pytest.fixture
def mock_rtltcp():
    proc = AsyncMock()
    proc.is_alive = True
    proc.start_with_retry = AsyncMock(return_value=True)
    proc.stop = AsyncMock()
    return proc


@pytest.fixture
def reader(sample_config, mock_rtlamr, mock_rtltcp):
    queue = asyncio.Queue()
    shutdown = asyncio.Event()
    return MeterReader(
        config=sample_config,
        rtlamr=mock_rtlamr,
        rtltcp=mock_rtltcp,
        reading_queue=queue,
        shutdown_event=shutdown,
        is_remote=False,
    )


class TestMeterReaderParsing:
    async def test_valid_reading_enqueued(self, reader, mock_rtlamr, sample_rtlamr_scm_line):
        """A valid SCM reading for a configured meter should be put on the queue."""
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_rtlamr_scm_line
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()

        assert reader.reading_queue.qsize() == 1
        reading = await reader.reading_queue.get()
        assert reading['meter_id'] == '33333333'
        assert reading['consumption'] == 1978226

    async def test_non_matching_id_not_enqueued(self, reader, mock_rtlamr):
        """Lines for meters not in config should be ignored."""
        non_matching_line = '{"Time":"2025-05-05T21:25:10Z","Offset":0,"Length":0,"Type":"R900","Message":{"ID":9999999,"Unkn1":163,"NoUse":0,"BackFlow":0,"Consumption":100,"Unkn3":0,"Leak":0,"LeakNow":0}}'
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return non_matching_line
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()
        assert reader.reading_queue.qsize() == 0

    async def test_non_json_line_ignored(self, reader, mock_rtlamr):
        """Non-JSON lines (rtlamr debug output) should be silently ignored."""
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 'set freq 912600155'
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()
        assert reader.reading_queue.qsize() == 0


class TestMeterReaderSleepCycle:
    async def test_sleep_cycle_when_all_meters_read(self, sample_config, mock_rtlamr, mock_rtltcp):
        """When sleep_for > 0 and all meters read, processes should be stopped then restarted."""
        sample_config['general']['sleep_for'] = 1
        queue = asyncio.Queue()
        shutdown = asyncio.Event()
        reader = MeterReader(
            config=sample_config,
            rtlamr=mock_rtlamr,
            rtltcp=mock_rtltcp,
            reading_queue=queue,
            shutdown_event=shutdown,
            is_remote=False,
        )

        scm_33 = '{"Time":"2025-05-05T21:25:11Z","Offset":0,"Length":0,"Type":"SCM","Message":{"ID":33333333,"Type":7,"TamperPhy":3,"TamperEnc":2,"Consumption":1978226,"ChecksumVal":60151}}'
        scm_22 = '{"Time":"2025-05-05T21:25:11Z","Offset":0,"Length":0,"Type":"SCM","Message":{"ID":22222222,"Type":7,"TamperPhy":0,"TamperEnc":1,"Consumption":9480653,"ChecksumVal":8042}}'

        call_count = 0
        cycle_count = 0
        async def fake_read_line():
            nonlocal call_count, cycle_count
            call_count += 1
            if cycle_count == 0:
                if call_count == 1:
                    return scm_33
                if call_count == 2:
                    return scm_22
            cycle_count += 1
            shutdown.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()

        # Both processes should have been stopped for sleep
        assert mock_rtlamr.stop.call_count >= 1
        assert mock_rtltcp.stop.call_count >= 1
        # Two readings should be on the queue
        assert queue.qsize() == 2


class TestMeterReaderMaxScanTime:
    SCM_33 = '{"Time":"2025-05-05T21:25:11Z","Offset":0,"Length":0,"Type":"SCM","Message":{"ID":33333333,"Type":7,"TamperPhy":3,"TamperEnc":2,"Consumption":1978226,"ChecksumVal":60151}}'

    def make_reader(self, sample_config, mock_rtlamr, mock_rtltcp, sleep_for, max_scan_time):
        sample_config['general']['sleep_for'] = sleep_for
        sample_config['general']['max_scan_time'] = max_scan_time
        return MeterReader(
            config=sample_config,
            rtlamr=mock_rtlamr,
            rtltcp=mock_rtltcp,
            reading_queue=asyncio.Queue(),
            shutdown_event=asyncio.Event(),
            is_remote=False,
        )

    async def test_sleeps_when_max_scan_time_reached(self, sample_config, mock_rtlamr, mock_rtltcp):
        """If not every meter is heard before max_scan_time, the reader should go to sleep anyway."""
        reader = self.make_reader(sample_config, mock_rtlamr, mock_rtltcp, sleep_for=60, max_scan_time=1)
        reader.max_scan_time = 0.1  # keep the test fast
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return self.SCM_33
            await asyncio.sleep(10)  # meter 22222222 is never heard
        mock_rtlamr.read_line = fake_read_line

        async def fake_sleep_cycle():
            reader.shutdown_event.set()
        reader._sleep_cycle = AsyncMock(side_effect=fake_sleep_cycle)

        await asyncio.wait_for(reader.run(), timeout=2)

        reader._sleep_cycle.assert_awaited_once()
        assert reader.reading_queue.qsize() == 1

    async def test_scan_window_restarts_each_cycle(self, sample_config, mock_rtlamr, mock_rtltcp):
        """Each wake-up should get a fresh max_scan_time window."""
        reader = self.make_reader(sample_config, mock_rtlamr, mock_rtltcp, sleep_for=60, max_scan_time=1)
        reader.max_scan_time = 0.1
        async def fake_read_line():
            await asyncio.sleep(10)
        mock_rtlamr.read_line = fake_read_line

        cycles = 0
        async def fake_sleep_cycle():
            nonlocal cycles
            cycles += 1
            if cycles == 2:
                reader.shutdown_event.set()
        reader._sleep_cycle = AsyncMock(side_effect=fake_sleep_cycle)

        await asyncio.wait_for(reader.run(), timeout=2)

        assert cycles == 2

    async def test_ignored_without_sleep_for(self, sample_config, mock_rtlamr, mock_rtltcp):
        """With sleep_for == 0 there is no sleep cycle, so max_scan_time must not end the reader."""
        reader = self.make_reader(sample_config, mock_rtlamr, mock_rtltcp, sleep_for=0, max_scan_time=300)
        assert reader.max_scan_time == 0

        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return self.SCM_33
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()

        assert reader.reading_queue.qsize() == 1


class TestMeterReaderListenMode:
    @pytest.fixture
    def listen_reader(self, sample_config, mock_rtlamr, mock_rtltcp):
        sample_config['general']['listen_mode'] = True
        sample_config['meters'] = {}
        shutdown = asyncio.Event()
        return MeterReader(
            config=sample_config,
            rtlamr=mock_rtlamr,
            rtltcp=mock_rtltcp,
            reading_queue=None,
            shutdown_event=shutdown,
            is_remote=False,
        )

    async def test_listen_mode_logs_not_enqueues(self, listen_reader, mock_rtlamr, sample_rtlamr_scm_line, caplog):
        """In listen mode, readings should be logged but never put on a queue."""
        import logging
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_rtlamr_scm_line
            listen_reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        with caplog.at_level(logging.INFO, logger='rtlamr2mqtt'):
            await listen_reader.run()

        assert any('33333333' in r.message for r in caplog.records)
        assert listen_reader.reading_queue is None

    async def test_listen_mode_deduplication(self, listen_reader, mock_rtlamr, sample_rtlamr_scm_line, caplog):
        """The same meter ID should only be logged once per session."""
        import logging
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return sample_rtlamr_scm_line  # same line twice
            listen_reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        with caplog.at_level(logging.INFO, logger='rtlamr2mqtt'):
            await listen_reader.run()

        new_meter_logs = [r for r in caplog.records if '33333333' in r.message]
        assert len(new_meter_logs) == 1

    async def test_listen_mode_accepts_unknown_meter(self, listen_reader, mock_rtlamr, caplog):
        """In listen mode, meters not in config should still be logged."""
        import logging
        unknown_line = '{"Time":"2025-05-05T21:25:10Z","Offset":0,"Length":0,"Type":"R900","Message":{"ID":9999999,"Unkn1":163,"NoUse":0,"BackFlow":0,"Consumption":100,"Unkn3":0,"Leak":0,"LeakNow":0}}'
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return unknown_line
            listen_reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        with caplog.at_level(logging.INFO, logger='rtlamr2mqtt'):
            await listen_reader.run()

        assert any('9999999' in r.message for r in caplog.records)


class TestMeterReaderProcessRestart:
    async def test_restart_on_rtlamr_death(self, reader, mock_rtlamr):
        """If rtlamr dies without the timeout signature, only rtlamr should restart."""
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # Simulate process death
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line
        mock_rtlamr.is_alive = False
        mock_rtlamr.recent_output = ['unexpected EOF']

        with patch('meter_reader.usbutil.reset_usb_device') as reset_usb:
            await reader.run()

        # Should have attempted to restart rtlamr
        assert mock_rtlamr.start_with_retry.call_count >= 1
        reset_usb.assert_not_called()

    async def test_shutdown_on_failed_restart(self, reader, mock_rtlamr):
        """If rtlamr can't restart, shutdown_event should be set."""
        mock_rtlamr.read_line = AsyncMock(return_value=None)
        mock_rtlamr.is_alive = False
        mock_rtlamr.start_with_retry = AsyncMock(return_value=False)

        await reader.run()

        assert reader.shutdown_event.is_set()

    async def test_timeout_signature_forces_rtltcp_recovery(
        self, reader, mock_rtlamr, mock_rtltcp
    ):
        """The rcvr.Read i/o timeout path should reset USB and restart rtl_tcp first."""
        call_count = 0

        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None
            reader.shutdown_event.set()
            return None

        mock_rtlamr.read_line = fake_read_line
        mock_rtlamr.is_alive = False
        mock_rtlamr.recent_output = [
            'time=2026-05-13T22:20:05.055-04:00 level=ERROR msg=receiver '
            'error="read tcp 127.0.0.1:58502->127.0.0.1:1234: i/o timeout',
            'rcvr.Read',
        ]

        with (
            patch('meter_reader.usbutil.reset_usb_device') as reset_usb,
            patch('meter_reader.usbutil.tickle_rtl_tcp', new=AsyncMock()) as tickle_rtl_tcp,
        ):
            await reader.run()

        mock_rtltcp.stop.assert_awaited()
        mock_rtltcp.start_with_retry.assert_awaited()
        reset_usb.assert_called_once_with(0)
        tickle_rtl_tcp.assert_awaited_once_with('127.0.0.1:1234')
        mock_rtlamr.start_with_retry.assert_awaited()

    async def test_usb_reset_failure_aborts_rtltcp_recovery(
        self, reader, mock_rtlamr, mock_rtltcp
    ):
        """If the USB device can't be found for reset, recovery should abort and
        shut down rather than starting rtl_tcp/rtlamr against hardware that may not
        actually be there (or was never truly reset)."""
        mock_rtlamr.read_line = AsyncMock(return_value=None)
        mock_rtlamr.is_alive = False
        mock_rtlamr.recent_output = [
            'time=2026-05-13T22:20:05.055-04:00 level=ERROR msg=receiver '
            'error="read tcp 127.0.0.1:58502->127.0.0.1:1234: i/o timeout',
            'rcvr.Read',
        ]

        with patch('meter_reader.usbutil.reset_usb_device', return_value=False) as reset_usb:
            await reader.run()

        reset_usb.assert_called_once_with(0)
        mock_rtltcp.start_with_retry.assert_not_awaited()
        mock_rtlamr.start_with_retry.assert_not_awaited()
        assert reader.shutdown_event.is_set()

    async def test_remote_timeout_signature_skips_local_usb_recovery(
        self, sample_config, mock_rtlamr, mock_rtltcp
    ):
        """Remote rtl_tcp should not try to stop/reset local USB on timeout."""
        queue = asyncio.Queue()
        shutdown = asyncio.Event()
        reader = MeterReader(
            config=sample_config,
            rtlamr=mock_rtlamr,
            rtltcp=mock_rtltcp,
            reading_queue=queue,
            shutdown_event=shutdown,
            is_remote=True,
        )
        call_count = 0

        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None
            reader.shutdown_event.set()
            return None

        mock_rtlamr.read_line = fake_read_line
        mock_rtlamr.is_alive = False
        mock_rtlamr.recent_output = ['i/o timeout', 'rcvr.Read']

        with patch('meter_reader.usbutil.reset_usb_device') as reset_usb:
            await reader.run()

        mock_rtltcp.stop.assert_not_awaited()
        mock_rtltcp.start_with_retry.assert_not_awaited()
        reset_usb.assert_not_called()
        mock_rtlamr.start_with_retry.assert_awaited()
