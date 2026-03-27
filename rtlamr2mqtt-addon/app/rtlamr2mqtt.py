#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rtlamr2mqtt - A Home Assistant add-on for RTLAMR
https://github.com/allangood/rtlamr2mqtt/blob/main/LICENSE

This add-on uses the code from:
- https://github.com/bemasher/rtlamr
- https://git.osmocom.org/rtl-sdr
"""

import asyncio
import os
import sys
import signal
import logging
from shutil import which

import helpers.config as cnf
import helpers.buildcmd as cmd
import helpers.usb_utils as usbutil
import helpers.info as i
from process_manager import ManagedProcess
from meter_reader import MeterReader
from mqtt_publisher import MQTTPublisher

# Logging verbosity map
VERBOSITY_MAP = {
    'none': logging.CRITICAL + 1,
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG,
}

logger = logging.getLogger('rtlamr2mqtt')


def setup_logging(verbosity: str):
    """Configure logging with the given verbosity level."""
    logging.basicConfig(
        format='[%(asctime)s] %(levelname)s: %(message)s',
        level=VERBOSITY_MAP.get(verbosity, logging.INFO),
    )
    logger.setLevel(VERBOSITY_MAP.get(verbosity, logging.INFO))


def load_and_validate_config():
    """Load config, set up logging, return config dict or exit."""
    if len(sys.argv) == 2:
        config_path = os.path.join(os.path.dirname(__file__), sys.argv[1])
    else:
        config_path = None

    status, msg, config = cnf.load_config(config_path)
    if status != 'success':
        # Use basic logging since we don't have config yet
        logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s')
        logger.critical(msg)
        sys.exit(1)

    setup_logging(config['general']['verbosity'])
    logger.info('Starting rtlamr2mqtt %s', i.version())
    logger.info(msg)
    return config


async def main():
    """Main async entry point."""
    config = load_and_validate_config()

    shutdown_event = asyncio.Event()
    reading_queue = asyncio.Queue(maxsize=100)

    # Signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    # Determine if rtl_tcp is remote
    rtltcp_host = config['general']['rtltcp_host']
    is_remote = rtltcp_host.split(':')[0] not in ['127.0.0.1', 'localhost']

    # USB setup (sync, before async work)
    if not is_remote and 'RTLAMR2MQTT_USE_MOCK' not in os.environ:
        device_index = config['general']['device_id']
        devices = usbutil.find_rtl_sdr_devices()
        if device_index >= len(devices):
            if len(devices) == 0:
                logger.critical('No RTL-SDR devices found')
            else:
                logger.critical('Device index %d out of range (found %d devices)', device_index, len(devices))
            sys.exit(1)
        logger.info('Found %d RTL-SDR device(s), using index %d', len(devices), device_index)

    # Build commands
    rtltcp_cmd = None
    if not is_remote:
        rtltcp_args = cmd.build_rtltcp_args(config)
        rtltcp_bin = which('rtl_tcp')
        if rtltcp_bin and rtltcp_args is not None:
            rtltcp_cmd = [rtltcp_bin] + rtltcp_args

    rtlamr_args = cmd.build_rtlamr_args(config)
    rtlamr_bin = which('rtlamr')
    if not rtlamr_bin:
        logger.critical('rtlamr binary not found in PATH')
        sys.exit(1)
    rtlamr_cmd = [rtlamr_bin] + rtlamr_args

    # USB reset callback for rtl_tcp retries (only when not using mock or remote)
    def reset_usb():
        if not is_remote and 'RTLAMR2MQTT_USE_MOCK' not in os.environ:
            device_index = config['general']['device_id']
            logger.info('Resetting USB device at index %d before retry', device_index)
            usbutil.reset_usb_device(device_index)

    # Create managed processes
    rtltcp_proc = ManagedProcess(
        name='rtl_tcp',
        command=rtltcp_cmd or ['echo', 'remote'],
        ready_pattern='listening...',
        ready_timeout=30.0,
        on_retry=reset_usb if not is_remote else None,
    )

    rtlamr_proc = ManagedProcess(
        name='rtlamr',
        command=rtlamr_cmd,
        ready_pattern='GainCount:',
        ready_timeout=30.0,
    )

    # Start rtl_tcp if local
    if not is_remote:
        if not await rtltcp_proc.start_with_retry():
            logger.critical('Failed to start rtl_tcp')
            sys.exit(1)

    # Tickle rtl_tcp to wake it up
    usbutil.tickle_rtl_tcp(rtltcp_host)

    # Start rtlamr
    if not await rtlamr_proc.start_with_retry():
        logger.critical('Failed to start rtlamr')
        if not is_remote:
            await rtltcp_proc.stop()
        sys.exit(1)

    # Create reader and publisher
    reader = MeterReader(
        config=config,
        rtlamr=rtlamr_proc,
        rtltcp=rtltcp_proc,
        reading_queue=reading_queue,
        shutdown_event=shutdown_event,
        is_remote=is_remote,
    )

    publisher = MQTTPublisher(
        config=config,
        reading_queue=reading_queue,
        shutdown_event=shutdown_event,
    )

    # Run reader and publisher concurrently
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(reader.run())
            tg.create_task(publisher.run())
    except* Exception as eg:
        for exc in eg.exceptions:
            if not isinstance(exc, asyncio.CancelledError):
                logger.error('Task error: %s', exc)

    # Cleanup
    logger.info('Shutting down...')
    await rtlamr_proc.stop()
    if not is_remote:
        await rtltcp_proc.stop()
    logger.info('Goodbye!')


if __name__ == '__main__':
    asyncio.run(main())
