import asyncio
import os
import pytest
from process_manager import ManagedProcess


@pytest.fixture
def mock_script_dir():
    return os.path.join(os.path.dirname(__file__), '..', 'mock')


class TestManagedProcessStart:
    async def test_start_with_ready_pattern(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
        )
        result = await proc.start()
        assert result is True
        assert proc.is_alive is True
        await proc.stop()

    async def test_start_timeout(self, tmp_path):
        # Script that never prints the ready pattern
        script = tmp_path / 'slow.sh'
        script.write_text('#!/bin/bash\nwhile true; do sleep 1; done\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='slow',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=1.0,
        )
        result = await proc.start()
        assert result is False
        assert proc.is_alive is False

    async def test_start_process_exits_early(self, tmp_path):
        script = tmp_path / 'fail.sh'
        script.write_text('#!/bin/bash\necho "error"\nexit 1\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='fail',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=5.0,
        )
        result = await proc.start()
        assert result is False


class TestManagedProcessStop:
    async def test_stop_terminates(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
        )
        await proc.start()
        await proc.stop()
        assert proc.is_alive is False

    async def test_stop_when_not_started(self):
        proc = ManagedProcess(
            name='test',
            command=['echo', 'hello'],
            ready_pattern='hello',
            ready_timeout=5.0,
        )
        # Should not raise
        await proc.stop()


class TestManagedProcessDrainOutput:
    @staticmethod
    def make_chatty_script(tmp_path):
        # After READY, write well past the pipe buffer plus asyncio's ~128 KB read buffer,
        # then leave a marker.
        # If nobody reads stdout, the writes block and the marker never appears.
        marker = tmp_path / 'done'
        script = tmp_path / 'chatty.sh'
        script.write_text(
            '#!/bin/bash\n'
            'echo "READY"\n'
            'for i in $(seq 1 20000); do echo "ll+, now $i padding-padding-padding"; done\n'
            f'touch {marker}\n'
            'while true; do sleep 1; done\n'
        )
        script.chmod(0o755)
        return script, marker

    async def wait_for_file(self, path, timeout):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            if path.exists():
                return True
            await asyncio.sleep(0.05)
        return False

    async def test_drain_keeps_pipe_from_filling(self, tmp_path):
        script, marker = self.make_chatty_script(tmp_path)
        proc = ManagedProcess(
            name='chatty',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=5.0,
            drain_output=True,
        )
        assert await proc.start() is True
        try:
            assert await self.wait_for_file(marker, timeout=5.0)
            assert proc.recent_output[-1].startswith('ll+, now 20000')
        finally:
            await proc.stop()
        assert proc.is_alive is False

    async def test_without_drain_pipe_fills_and_blocks(self, tmp_path):
        """Guards the test above: proves the script really does block when not drained."""
        script, marker = self.make_chatty_script(tmp_path)
        proc = ManagedProcess(
            name='chatty',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=5.0,
        )
        assert await proc.start() is True
        try:
            assert not await self.wait_for_file(marker, timeout=1.0)
        finally:
            await proc.stop()


class TestManagedProcessReadLine:
    async def test_read_lines_from_mock_rtlamr(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtlamr',
            command=[os.path.join(mock_script_dir, 'rtlamr')],
            ready_pattern='GainCount',
            ready_timeout=10.0,
        )
        await proc.start()
        # Read a few lines — the mock outputs JSON lines after the header
        lines_read = []
        for _ in range(3):
            line = await proc.read_line()
            if line is not None:
                lines_read.append(line)
        assert len(lines_read) > 0
        await proc.stop()

    async def test_read_line_returns_none_after_exit(self, tmp_path):
        script = tmp_path / 'quick.sh'
        script.write_text('#!/bin/bash\necho "READY"\necho "line1"\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='quick',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=5.0,
        )
        await proc.start()
        # Read until we get None (process exited)
        lines = []
        for _ in range(10):
            line = await proc.read_line()
            if line is None:
                break
            lines.append(line)
        assert 'line1' in lines
        assert proc.is_alive is False


class TestManagedProcessRetry:
    async def test_start_with_retry_succeeds(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
            max_retries=3,
            backoff=[0.1, 0.2, 0.3],
        )
        result = await proc.start_with_retry()
        assert result is True
        await proc.stop()

    async def test_on_retry_callback_called(self, tmp_path):
        script = tmp_path / 'fail.sh'
        script.write_text('#!/bin/bash\nexit 1\n')
        script.chmod(0o755)
        callback_count = 0
        def on_retry():
            nonlocal callback_count
            callback_count += 1
        proc = ManagedProcess(
            name='fail',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=1.0,
            max_retries=3,
            backoff=[0.1, 0.1, 0.1],
            on_retry=on_retry,
        )
        result = await proc.start_with_retry()
        assert result is False
        assert callback_count == 3

    async def test_on_retry_not_called_on_first_attempt(self, mock_script_dir):
        callback_count = 0
        def on_retry():
            nonlocal callback_count
            callback_count += 1
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
            on_retry=on_retry,
        )
        result = await proc.start_with_retry()
        assert result is True
        assert callback_count == 0
        await proc.stop()

    async def test_async_on_retry_callback_is_awaited(self, tmp_path):
        """on_retry may be a coroutine function (e.g. the USB reset helper) —
        it must be awaited, not fired-and-forgotten as an unawaited coroutine."""
        script = tmp_path / 'fail.sh'
        script.write_text('#!/bin/bash\nexit 1\n')
        script.chmod(0o755)
        callback_count = 0

        async def on_retry():
            nonlocal callback_count
            await asyncio.sleep(0)
            callback_count += 1

        proc = ManagedProcess(
            name='fail',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=1.0,
            max_retries=3,
            backoff=[0.1, 0.1, 0.1],
            on_retry=on_retry,
        )
        result = await proc.start_with_retry()
        assert result is False
        assert callback_count == 3

    async def test_start_with_retry_exhausted(self, tmp_path):
        script = tmp_path / 'fail.sh'
        script.write_text('#!/bin/bash\nexit 1\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='fail',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=1.0,
            max_retries=2,
            backoff=[0.1, 0.1],
        )
        result = await proc.start_with_retry()
        assert result is False


class TestManagedProcessRestart:
    async def test_restart(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
        )
        await proc.start()
        assert proc.is_alive is True
        result = await proc.restart()
        assert result is True
        assert proc.is_alive is True
        await proc.stop()
