"""
Generic async subprocess manager with ready detection, retry, and clean shutdown.
"""

import asyncio
import os
import signal
import logging
from typing import Callable
from shutil import which

logger = logging.getLogger('rtlamr2mqtt')

# Cache stdbuf path at module load time
_stdbuf_path = which('stdbuf')


class ManagedProcess:
    """
    Manages an external process with:
    - Async start with ready-pattern detection
    - Timeout on ready wait
    - Retry with configurable backoff
    - Clean shutdown (SIGTERM -> SIGKILL)
    - Async line reading
    """

    def __init__(
        self,
        name: str,
        command: list[str],
        ready_pattern: str,
        ready_timeout: float = 30.0,
        max_retries: int = 5,
        backoff: list[float] | None = None,
        on_retry: Callable | None = None,
    ):
        self.name = name
        self.command = command
        self.ready_pattern = ready_pattern
        self.ready_timeout = ready_timeout
        self.max_retries = max_retries
        self.backoff = backoff if backoff is not None else [2, 5, 10, 20, 30]
        self.on_retry = on_retry
        self._process: asyncio.subprocess.Process | None = None

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> bool:
        """
        Start the process and wait for the ready pattern in stdout.
        Returns True if the process started and is ready, False otherwise.
        """
        if self.is_alive:
            await self.stop()

        # Prepend stdbuf for line-buffered output if available
        full_command = list(self.command)
        if _stdbuf_path:
            full_command = [_stdbuf_path, '-oL'] + full_command

        logger.info('Starting %s: %s', self.name, ' '.join(full_command))

        try:
            self._process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as e:
            logger.error('Failed to launch %s: %s', self.name, e)
            self._process = None
            return False

        # Wait for ready pattern with timeout
        try:
            ready = await asyncio.wait_for(
                self._wait_for_ready(),
                timeout=self.ready_timeout,
            )
            if ready:
                logger.info('%s is ready', self.name)
            return ready
        except asyncio.TimeoutError:
            logger.error('%s did not become ready within %.1fs', self.name, self.ready_timeout)
            await self.stop()
            return False

    async def _wait_for_ready(self) -> bool:
        """
        Read stdout lines until the ready pattern is found or the process exits.
        """
        while True:
            if self._process.stdout is None:
                return False

            line_bytes = await self._process.stdout.readline()
            if not line_bytes:
                # EOF — process exited
                logger.error('%s exited before becoming ready (exit code: %s)',
                             self.name, self._process.returncode)
                return False

            line = line_bytes.decode('utf-8', errors='replace').strip()
            if line:
                logger.debug('%s: %s', self.name, line)
            if self.ready_pattern in line:
                return True

    async def stop(self):
        """
        Stop the process. Sends SIGTERM, waits 2 seconds, then SIGKILL.
        """
        if self._process is None:
            return

        if self._process.returncode is not None:
            # Already exited
            self._process = None
            return

        logger.info('Stopping %s (pid %d)', self.name, self._process.pid)

        try:
            # Signal the entire process group (includes stdbuf child)
            os.killpg(self._process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning('%s did not exit after SIGTERM, sending SIGKILL', self.name)
                try:
                    os.killpg(self._process.pid, signal.SIGKILL)
                except (ProcessLookupError, BrokenPipeError):
                    self._process.kill()
                await self._process.wait()
        except (ProcessLookupError, BrokenPipeError):
            pass  # Already dead

        logger.info('%s stopped', self.name)
        self._process = None

    async def restart(self) -> bool:
        """
        Stop then start the process.
        """
        await self.stop()
        return await self.start()

    async def start_with_retry(self) -> bool:
        """
        Try to start the process, retrying with backoff on failure.
        Returns True if the process started successfully, False if all retries exhausted.
        """
        if await self.start():
            return True

        for attempt in range(self.max_retries):
            delay = self.backoff[min(attempt, len(self.backoff) - 1)]
            logger.warning(
                '%s failed to start, retry %d/%d in %.1fs',
                self.name, attempt + 1, self.max_retries, delay,
            )
            if self.on_retry:
                try:
                    self.on_retry()
                except Exception as e:
                    logger.warning('on_retry callback for %s failed: %s', self.name, e)
            await asyncio.sleep(delay)
            if await self.start():
                return True

        logger.error('%s failed to start after %d retries', self.name, self.max_retries)
        return False

    async def read_line(self) -> str | None:
        """
        Read one line from the process stdout.
        Returns the stripped line string, or None if the process has exited / stdout closed.
        """
        if self._process is None or self._process.stdout is None:
            return None

        try:
            line_bytes = await self._process.stdout.readline()
        except Exception as e:
            logger.error('Error reading from %s: %s', self.name, e)
            return None

        if not line_bytes:
            # EOF
            return None

        return line_bytes.decode('utf-8', errors='replace').strip()

    async def wait_for_exit(self):
        """
        Wait for the process to exit. Used during intentional shutdown.
        """
        if self._process is not None and self._process.returncode is None:
            await self._process.wait()
