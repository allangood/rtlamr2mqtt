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


class TestMeterReaderProcessRestart:
    async def test_restart_on_rtlamr_death(self, reader, mock_rtlamr):
        """If rtlamr dies (read_line returns None), it should be restarted."""
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

        await reader.run()

        # Should have attempted to restart rtlamr
        assert mock_rtlamr.start_with_retry.call_count >= 1

    async def test_shutdown_on_failed_restart(self, reader, mock_rtlamr):
        """If rtlamr can't restart, shutdown_event should be set."""
        mock_rtlamr.read_line = AsyncMock(return_value=None)
        mock_rtlamr.is_alive = False
        mock_rtlamr.start_with_retry = AsyncMock(return_value=False)

        await reader.run()

        assert reader.shutdown_event.is_set()
