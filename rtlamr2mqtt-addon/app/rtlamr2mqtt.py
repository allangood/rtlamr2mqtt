#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rtlamr2mqtt - A Home Assistant add-on for RTLAMR
https://github.com/allangood/rtlamr2mqtt/blob/main/LICENSE

This add-on uses the code from:
- https://github.com/bemasher/rtlamr
- https://git.osmocom.org/rtl-sdr
"""

import os
import sys
import logging
import subprocess
import signal
from subprocess import Popen, PIPE
from json import dumps
from time import sleep
import helpers.config as cnf
import helpers.buildcmd as cmd
import helpers.mqtt_client as m
import helpers.read_output as ro
import helpers.usb_utils as usbutil


def shutdown(rtlamr=None, rtltcp=None, mqtt_client=None):
    if LOG_LEVEL >= 3:
        logger.info('Shutting down...')
    # Terminate RTLAMR
    if rtlamr is not None:
        if LOG_LEVEL >= 3:
            logger.info('Terminating RTLAMR...')
        rtlamr.terminate()
        try:
            rtlamr.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            rtlamr.kill()
            rtlamr.communicate()
        if LOG_LEVEL >= 3:
            logger.info('RTLAMR Terminitaed.')
    # Terminate RTL_TCP
    if rtltcp is not None:
        if LOG_LEVEL >= 3:
            logger.info('Terminating RTL_TCP...')
        rtltcp.terminate()
        try:
            rtltcp.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            rtltcp.kill()
            rtltcp.communicate()
        if LOG_LEVEL >= 3:
            logger.info('RTL_TCP Terminitaed.')
    if mqtt_client is not None:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    if LOG_LEVEL >= 3:
        logger.info('All done. Bye!')



def signal_handler(signum, frame):
    raise Exception(f'Signal {signum} received.')



def on_message(client, userdata, message):
    if LOG_LEVEL >= 3:
        logger.info('Received message "%s" on topic "%s"', message.payload.decode(), message.topic)



def start_rtltcp(config):
    # Search for RTL-SDR devices
    usb_id_list = usbutil.find_rtl_sdr_devices()

    if 'RTLAMR2MQTT_USE_MOCK' in os.environ:
        usb_id_list = [ '001:001']

    if config['general']['device_id'] == '0':
        if len(usb_id_list) > 0:
            usb_id = usb_id_list[0]
        else:
            logger.critical('No RTL-SDR devices found. Exiting...')
            return None
    else:
        usb_id = config['general']['device_id']

    if LOG_LEVEL >= 3:
        logger.debug('Reseting USB device: %s', usb_id)
    
    if 'RTLAMR2MQTT_USE_MOCK' not in os.environ:
        usbutil.reset_usb_device(usb_id)

    rtltcp_args = cmd.build_rtltcp_args(config)

    if LOG_LEVEL >= 3:
        logger.info('Starting RTL_TCP using "rtl_tcp %s"', " ".join(rtltcp_args))
    try:
        rtltcp = Popen(["rtl_tcp"] + rtltcp_args, close_fds=True, stdout=PIPE)
    except Exception as e:
        logger.critical('Failed to start RTL_TCP. %s', e)
        return None
    rtltcp_is_ready = False
    # Wait for rtl_tcp to be ready
    while not rtltcp_is_ready:
        # Read the output in chunks
        try:
            rtltcp_output = rtltcp.stdout.read1().decode('utf-8').strip('\n')
        except KeyboardInterrupt:
            logger.critical('Interrupted by user.')
            rtltcp_is_ready = False
            sys.exit(1)
        except Exception as e:
            logger.critical(e)
            rtltcp_is_ready = False
            sys.exit(1)
        if rtltcp_output:
            if LOG_LEVEL >= 4:
                logger.debug(rtltcp_output)
            if "listening..." in rtltcp_output:
                rtltcp_is_ready = True
                if LOG_LEVEL >= 3:
                    logger.info('RTL_TCP started!')
        # Check rtl_tcp status
        rtltcp.poll()
        if rtltcp.returncode is not None:
            logger.critical('RTL_TCP failed to start errcode: %d', int(rtltcp.returncode))
            sys.exit(1)
    return rtltcp



def start_rtlamr(config):
    rtlamr_args = cmd.build_rtlamr_args(config)
    if LOG_LEVEL >= 3:
        logger.info('Starting RTLAMR using "rtlamr %s"', " ".join(rtlamr_args))
    try:
        rtlamr = Popen(["rtlamr"] + rtlamr_args, close_fds=True, stdout=PIPE)
    except Exception:
        logger.critical('Failed to start RTLAMR. Exiting...')
        return None
    rtlamr_is_ready = False
    while not rtlamr_is_ready:
        try:
            rtlamr_output = rtlamr.stdout.read1().decode('utf-8').strip('\n')
        except KeyboardInterrupt:
            logger.critical('Interrupted by user.')
            rtlamr_is_ready = False
            sys.exit(1)
        except Exception as e:
            logger.critical(e)
            rtlamr_is_ready = False
            sys.exit(1)
        if rtlamr_output:
            if LOG_LEVEL >= 4:
                logger.debug(rtlamr_output)
            if 'set gain mode' in rtlamr_output:
                rtlamr_is_ready = True
                if LOG_LEVEL >= 3:
                    logger.info('RTLAMR started!')
        # Check rtl_tcp status
        rtlamr.poll()
        if rtlamr.returncode is not None:
            logger.critical('RTLAMR failed to start errcode: %d', rtlamr.returncode)
            sys.exit(1)
    return rtlamr



def main():
    """
    Main function
    """
    # Signal handlers/call back
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Load the configuration file
    if len(sys.argv) == 2:
        config_path = os.path.join(os.path.dirname(__file__), sys.argv[1])
    else:
        config_path = None
    err, msg, config = cnf.load_config(config_path)
    if err != 'success':
        # Error loading configuration file
        logger.critical(msg)
        sys.exit(1)
    # Configuration file loaded successfully
    # Use LOG_LEVEL as a global variable
    global LOG_LEVEL
    # Convert verbosity to a number and store as LOG_LEVEL
    LOG_LEVEL = ['none', 'error', 'warning', 'info', 'debug'].index(config['general']['verbosity'])
    if LOG_LEVEL >= 3:
        logger.info(msg)
    ##################################################################

    # Get a list of meters ids to watch
    meter_ids_list = cmd.get_comma_separated_str('id', config['meters']).split(',')

    # Create MQTT Client and connect to the broker
    mqtt_client = m.MQTTClient(
        broker=config['mqtt']['host'],
        port=config['mqtt']['port'],
        username=config['mqtt']['user'],
        password=config['mqtt']['password'],
        tls_enabled=config['mqtt']['tls_enabled'],
        tls_insecure=config['mqtt']['tls_insecure'],
        ca_cert=config['mqtt']['tls_ca'],
        client_cert=config['mqtt']['tls_cert'],
        client_key=config['mqtt']['tls_keyfile'],
        log_level=LOG_LEVEL,
        logger=logger,
    )

    # Set Last Will and Testament
    mqtt_client.set_last_will(
        topic=f'{config["mqtt"]["base_topic"]}/status',
        payload="offline",
        qos=1,
        retain=True
    )

    try:
        mqtt_client.connect()
    except Exception as e:
        logger.critical('Failed to connect to MQTT broker: %s', e)
        sys.exit(1)

    # Set on_message callback
    mqtt_client.set_on_message_callback(on_message)
    # Subscribe to Home Assistant status topic
    mqtt_client.subscribe(config['mqtt']['ha_status_topic'], qos=1)
    # Start the MQTT client loop
    mqtt_client.loop_start()
    # Publish the initial status
    mqtt_client.publish(
        topic=f'{config["mqtt"]["base_topic"]}/status',
        payload='online',
        qos=1,
        retain=True
    )
    ##################################################################
    keep_reading = True
    while keep_reading:
        missing_readings = meter_ids_list.copy()
        # Start RTL_TCP
        rtltcp = start_rtltcp(config)
        if rtltcp is None:
            logger.critical('Failed to start RTL_TCP. Exiting...')
            shutdown(rtlamr=None, rtltcp=None, mqtt_client=mqtt_client)
            sys.exit(1)

        # Start RTLAMR
        rtlamr = start_rtlamr(config)
        if rtlamr is None:
            logger.critical('Failed to start RTLAMR. Exiting...')
            shutdown(rtlamr=None, rtltcp=rtltcp, mqtt_client=mqtt_client)
            sys.exit(1)
        ##################################################################

        # Read the output from RTLAMR
        while keep_reading:
            try:
                rtlamr_output = rtlamr.stdout.read1().decode('utf-8')
            except KeyboardInterrupt:
                logger.critical('Interrupted by user.')
                keep_reading = False
                break
            except Exception as e:
                logger.critical(e)
                keep_reading = False
                break
            # Search for ID in the output
            reading = ro.search_for_ids(
                rtlamr_output = rtlamr_output,
                meter_ids_list = meter_ids_list
            )
            if reading is not None:
                # Remove the meter_id from the list of missing readings
                if reading['meter_id'] in missing_readings:
                    missing_readings.remove(reading['meter_id'])
                # Publish the reading to MQTT
                mqtt_client.publish(
                    topic=f'{config["mqtt"]["base_topic"]}/{reading["meter_id"]}',
                    payload=dumps(reading),
                    qos=1,
                    retain=True
                )

            if config['general']['sleep_for'] > 0 and len(missing_readings) == 0:
                # We have our readings, so we can sleep
                if LOG_LEVEL >= 3:
                    logger.info(f'All readings received. Sleeping for {config["general"]["sleep_for"]} seconds...')
                # Shutdown everything, but mqtt_client
                shutdown(rtlamr=rtlamr, rtltcp=rtltcp, mqtt_client=None)
                try:
                    sleep(int(config['general']['sleep_for']))
                except KeyboardInterrupt:
                    logger.critical('Interrupted by user.')
                    keep_reading = False
                    shutdown(rtlamr=rtlamr, rtltcp=rtltcp, mqtt_client=mqtt_client)
                    break
                except Exception:
                    logger.critical('Term siganal received. Exiting...')
                    keep_reading = False
                    shutdown(rtlamr=rtlamr, rtltcp=rtltcp, mqtt_client=mqtt_client)
                    break
                if LOG_LEVEL >= 3:
                    logger.info('Time to wake up!')
                break

    # Shutdown
    mqtt_client.publish(
                topic=f'{config["mqtt"]["base_topic"]}/status',
                payload='offline',
                qos=1,
                retain=True
            )
    shutdown(rtlamr = rtlamr, rtltcp = rtltcp, mqtt_client = mqtt_client)


if __name__ == '__main__':
    # Set up logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.DEBUG)
    LOG_LEVEL = 0
    # Call main function
    main()
