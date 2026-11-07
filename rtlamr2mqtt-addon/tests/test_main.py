import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import rtlamr2mqtt


class FakeTask:
    """Stands in for MeterReader / MQTTPublisher: run() executes the given behaviour."""

    def __init__(self, behaviour, **kwargs):
        self.kwargs = kwargs
        self.behaviour = behaviour

    async def run(self):
        await self.behaviour(self)


@pytest.fixture
def run_main(sample_config):
    # Remote rtl_tcp skips USB discovery and the local rtl_tcp process
    sample_config['general']['rtltcp_host'] = '10.0.0.5:1234'
    signal_handlers = []

    async def _run(reader_behaviour, publisher_behaviour=None):
        loop = asyncio.get_running_loop()

        async def idle(task):
            await task.kwargs['shutdown_event'].wait()

        proc = MagicMock()
        proc.start_with_retry = AsyncMock(return_value=True)
        proc.stop = AsyncMock()

        with patch.object(rtlamr2mqtt, 'load_and_validate_config', return_value=sample_config), \
             patch.object(rtlamr2mqtt, 'which', return_value='/usr/bin/rtlamr'), \
             patch.object(rtlamr2mqtt, 'ManagedProcess', return_value=proc), \
             patch.object(rtlamr2mqtt.usbutil, 'tickle_rtl_tcp', AsyncMock()), \
             patch.object(rtlamr2mqtt, 'MeterReader',
                          side_effect=lambda **kw: FakeTask(reader_behaviour, **kw)), \
             patch.object(rtlamr2mqtt, 'MQTTPublisher',
                          side_effect=lambda **kw: FakeTask(publisher_behaviour or idle, **kw)), \
             patch.object(loop, 'add_signal_handler',
                          side_effect=lambda sig, cb: signal_handlers.append(cb)):
            await rtlamr2mqtt.main()

    # Behaviours can simulate SIGTERM by calling run_main.signal_handlers[0]()
    _run.signal_handlers = signal_handlers
    return _run


class TestMainExitCode:
    async def test_requested_shutdown_exits_cleanly(self, run_main):
        async def receive_sigterm(task):
            run_main.signal_handlers[0]()

        await run_main(receive_sigterm)  # no SystemExit raised

    async def test_reader_giving_up_exits_non_zero(self, run_main):
        """e.g. rtlamr could not be restarted: the reader sets shutdown and returns."""
        async def give_up(task):
            task.kwargs['shutdown_event'].set()

        with pytest.raises(SystemExit) as exc:
            await run_main(give_up)
        assert exc.value.code == 1

    async def test_publisher_crash_exits_non_zero(self, run_main):
        async def idle(task):
            await task.kwargs['shutdown_event'].wait()

        async def crash(task):
            raise RuntimeError('boom')

        with pytest.raises(SystemExit) as exc:
            await run_main(idle, crash)
        assert exc.value.code == 1
