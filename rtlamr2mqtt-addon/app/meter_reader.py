"""
Async meter reader: reads rtlamr output, parses readings, enqueues them.
Handles sleep/wake cycle and process restart on failure.
"""

import asyncio
import logging

import helpers.read_output as ro
import helpers.usb_utils as usbutil

logger = logging.getLogger('rtlamr2mqtt')


class MeterReader:
    """
    Reads lines from the rtlamr ManagedProcess, parses meter readings,
    and puts them on the reading queue for the MQTT publisher.
    """

    def __init__(
        self,
        config: dict,
        rtlamr,
        rtltcp,
        reading_queue: asyncio.Queue,
        shutdown_event: asyncio.Event,
        is_remote: bool,
    ):
        self.config = config
        self.rtlamr = rtlamr
        self.rtltcp = rtltcp
        self.reading_queue = reading_queue
        self.shutdown_event = shutdown_event
        self.is_remote = is_remote
        self.meter_ids = list(config['meters'].keys())
        self.sleep_for = config['general']['sleep_for']
        self.rtltcp_host = config['general']['rtltcp_host']

    async def run(self):
        """
        Main reading loop. Reads from rtlamr, parses, enqueues.
        Handles sleep/wake cycle and process restarts.
        """
        while not self.shutdown_event.is_set():
            meters_seen = set()

            # Read until shutdown or all meters seen (when sleep_for > 0)
            while not self.shutdown_event.is_set():
                line = await self.rtlamr.read_line()

                if line is None:
                    # Process died or stdout closed
                    if self.shutdown_event.is_set():
                        break
                    if not self.rtlamr.is_alive:
                        logger.warning('rtlamr process died, attempting restart')
                        if not await self.rtlamr.start_with_retry():
                            logger.error('Failed to restart rtlamr, shutting down')
                            self.shutdown_event.set()
                            return
                    else:
                        # stdout closed but process alive — avoid tight loop
                        await asyncio.sleep(0.1)
                    continue

                if not line:
                    # Empty line
                    continue

                # Parse the line
                reading = ro.get_message_for_ids(line, self.meter_ids)
                if reading is None:
                    continue

                # Enqueue the reading
                try:
                    self.reading_queue.put_nowait(reading)
                except asyncio.QueueFull:
                    # Drop oldest reading to make room
                    try:
                        self.reading_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self.reading_queue.put_nowait(reading)
                    logger.warning('Reading queue full, dropped oldest reading')

                meters_seen.add(reading['meter_id'])
                logger.debug('Meter %s reading: %s', reading['meter_id'], reading['consumption'])

                # Check if all meters have been read (sleep_for mode)
                if self.sleep_for > 0 and meters_seen == set(self.meter_ids):
                    logger.info('All %d meters read', len(self.meter_ids))
                    break

            # Sleep/wake cycle
            if self.sleep_for > 0 and not self.shutdown_event.is_set():
                await self._sleep_cycle()

            # If sleep_for == 0 and we got here, the inner loop broke due to shutdown
            if self.sleep_for == 0:
                break

    async def _sleep_cycle(self):
        """
        Stop processes, sleep, restart processes.
        """
        logger.info('Stopping processes for sleep cycle')
        await self.rtlamr.stop()
        if not self.is_remote:
            await self.rtltcp.stop()

        logger.info('Sleeping for %d seconds', self.sleep_for)

        # Cancellable sleep
        sleep_task = asyncio.create_task(asyncio.sleep(self.sleep_for))
        shutdown_task = asyncio.create_task(self.shutdown_event.wait())
        done, pending = await asyncio.wait(
            [sleep_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self.shutdown_event.is_set():
            return

        logger.info('Waking up, restarting processes')

        # Restart rtl_tcp first (if local)
        if not self.is_remote:
            if not await self.rtltcp.start_with_retry():
                logger.error('Failed to restart rtl_tcp after sleep, shutting down')
                self.shutdown_event.set()
                return

        # Tickle rtl_tcp to wake up the receiver
        usbutil.tickle_rtl_tcp(self.rtltcp_host)

        # Restart rtlamr
        if not await self.rtlamr.start_with_retry():
            logger.error('Failed to restart rtlamr after sleep, shutting down')
            self.shutdown_event.set()
            return
