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
from datetime import datetime
from json import dumps
from time import sleep, time
import helpers.config as cnf
import helpers.buildcmd as cmd
import helpers.mqtt_client as m
import helpers.ha_messages as ha_msgs
import helpers.read_output as ro
import helpers.usb_utils as usbutil
import helpers.info as i


# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.DEBUG)
LOG_LEVEL = 0
logger.info('Starting rtlamr2mqtt %s', i.version())



def shutdown(rtlamr=None, rtltcp=None, mqtt_client=None, base_topic='rtlamr'):
    """ Shutdown function to terminate processes and clean up """
    if LOG_LEVEL >= 3:
        logger.info('Shutting down...')
    # Terminate RTLAMR
    if rtlamr is not None:
        if LOG_LEVEL >= 3:
            logger.info('Terminating RTLAMR...')
        rtlamr.stdout.close()
        rtlamr.terminate()
        try:
            rtlamr.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            rtlamr.kill()
            rtlamr.communicate()
        if LOG_LEVEL >= 3:
            logger.info('RTLAMR Terminitaed.')
    # Terminate RTL_TCP
    if rtltcp not in [None, 'remote']:
        if LOG_LEVEL >= 3:
            logger.info('Terminating RTL_TCP...')
        rtltcp.stdout.close()
        rtltcp.terminate()
        try:
            rtltcp.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            rtltcp.kill()
            rtltcp.communicate()
        if LOG_LEVEL >= 3:
            logger.info('RTL_TCP Terminitaed.')
    if mqtt_client is not None:
        mqtt_client.publish(
            topic=f'{base_topic}/status',
            payload='offline',
            qos=1,
            retain=False
        )
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    if LOG_LEVEL >= 3:
        logger.info('All done. Bye!')



def signal_handler(signum, frame):
    """ Signal handler for SIGINT and SIGTERM """
    raise RuntimeError(f'Signal {signum} received.')




def on_message(client, userdata, message):
    """ Callback function for MQTT messages """
    if LOG_LEVEL >= 3:
        logger.info('Received message "%s" on topic "%s"', message.payload.decode(), message.topic)



def get_iso8601_timestamp():
    """
    Get the current timestamp in ISO 8601 format
    """
    return datetime.now().astimezone().replace(microsecond=0).isoformat()



def start_rtltcp(config):
    """ Start RTL_TCP process """
    # Search for RTL-SDR devices
    usb_id_list = usbutil.find_rtl_sdr_devices()

    # Check if we are using a remote RTL_TCP server
    is_remote = config["general"]["rtltcp_host"].split(':') not in [ '127.0.1', 'localhost' ]

    if 'RTLAMR2MQTT_USE_MOCK' in os.environ or is_remote:
        usb_id_list = [ '001:001']

    usb_id = config['general']['device_id']
    if config['general']['device_id'] == '0':
        if len(usb_id_list) > 0:
            usb_id = usb_id_list[0]
        else:
            logger.critical('No RTL-SDR devices found. Exiting...')
            return None


    if 'RTLAMR2MQTT_USE_MOCK' not in os.environ and not is_remote:
        if LOG_LEVEL >= 3:
            logger.debug('Reseting USB device: %s', usb_id)
        usbutil.reset_usb_device(usb_id)

    rtltcp_args = cmd.build_rtltcp_args(config)
    if rtltcp_args is None and LOG_LEVEL >= 3:
        logger.info(f'Using remote RTL_TCP host on {config["general"]["rtltcp_host"]}.')
        return 'remote'

    if LOG_LEVEL >= 3:
        logger.info('Starting RTL_TCP using: rtl_tcp %s', " ".join(rtltcp_args))
    try:
        rtltcp = subprocess.Popen(["rtl_tcp"] + rtltcp_args,
            start_new_session=True,
            text=True,
            close_fds=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        sleep(2)
    except Exception as e:
        logger.critical('Failed to start RTL_TCP. %s', e)
        return None

    rtltcp_is_ready = False
    # Wait for rtl_tcp to be ready
    while not rtltcp_is_ready:
        # Read the output in chunks
        try:
            usbutil.tickle_rtl_tcp(config['general']['rtltcp_host'])
            rtltcp_output = rtltcp.stdout.readline().strip()
            sys.stdout.flush()
        except Exception as e:
            logger.critical(e)
            rtltcp_is_ready = False
            return None
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
    """ Start RTLAMR process """
    rtlamr_args = cmd.build_rtlamr_args(config)
    usbutil.tickle_rtl_tcp(config['general']['rtltcp_host'])
    if LOG_LEVEL >= 3:
        logger.info('Starting RTLAMR using: rtlamr %s', " ".join(rtlamr_args))
    try:
        rtlamr = subprocess.Popen(["rtlamr"] + rtlamr_args,
            close_fds=True,
            text=True,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            )
        sleep(2)
    except Exception:
        logger.critical('Failed to start RTLAMR. Exiting...')
        return None
    rtlamr_is_ready = False
    while not rtlamr_is_ready:
        try:
            rtlamr_output = rtlamr.stdout.readline().strip()
        except Exception as e:
            logger.critical(e)
            rtlamr_is_ready = False
            return None
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

    # ToDo:
    # Here is were it will be defined how the code will search
    # for a meter_id based on a value.
    # res = list((sub for sub in config['meters'] if config['meters'][sub]['name'][-7:] == "_FINDME"))

    # Get a list of meters ids to watch
    meter_ids_list = list(config['meters'].keys())

    # Create the info reading variable
    # This variable stores the number of readings for each meter
    # It is used to help with the sleep_for logic
    reading_info = {}
    for m_id in meter_ids_list:
        reading_info[m_id] = { 'n_readings': 0, 'last_reading': 0 }

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
        retain=False
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

    # Publish the discovery messages for all meters
    for meter in config['meters']:
        discovery_payload = ha_msgs.meter_discover_payload(config["mqtt"]["base_topic"], config['meters'][meter])
        mqtt_client.publish(
            topic=f'{config["mqtt"]["ha_autodiscovery_topic"]}/device/{meter}/config',
            payload=dumps(discovery_payload),
            qos=1,
            retain=False
        )

    # Give some time for the MQTT client to connect and publish
    sleep(1)
    # Publish the initial status
    mqtt_client.publish(
        topic=f'{config["mqtt"]["base_topic"]}/status',
        payload='online',
        qos=1,
        retain=False
    )

    ##################################################################
    keep_reading = True
    while keep_reading:
        read_counter = []
        # Start RTL_TCP
        rtltcp = start_rtltcp(config)
        if rtltcp is None:
            logger.critical('Failed to start RTL_TCP. Exiting...')
            shutdown(rtlamr=None, rtltcp=None, mqtt_client=mqtt_client, base_topic=config["mqtt"]["base_topic"])
            sys.exit(1)

        # Start RTLAMR
        rtlamr = start_rtlamr(config)
        if rtlamr is None:
            logger.critical('Failed to start RTLAMR. Exiting...')
            shutdown(rtlamr=None, rtltcp=rtltcp, mqtt_client=mqtt_client, base_topic=config["mqtt"]["base_topic"])
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
            reading = ro.get_message_for_ids(
                rtlamr_output = rtlamr_output,
                meter_ids_list = meter_ids_list
            )

            if reading is not None:
                # Add the meter_id to the read_counter
                if reading['meter_id'] not in read_counter:
                    read_counter.append(reading['meter_id'])

                # Update the reading info
                reading_info[reading['meter_id']]['n_readings'] += 1
                reading_info[reading['meter_id']]['last_reading'] = int(time())

                if config['meters'][reading['meter_id']]['format'] is not None:
                    r = ro.format_number(reading['consumption'], config['meters'][reading['meter_id']]['format'])
                else:
                    r = reading['consumption']

                # Publish the reading to MQTT
                payload = { 'reading': r, 'lastseen': get_iso8601_timestamp() }
                mqtt_client.publish(
                    topic=f'{config["mqtt"]["base_topic"]}/{reading["meter_id"]}/state',
                    payload=dumps(payload),
                    qos=1,
                    retain=False
                )

                # Publish the meter attributes to MQTT
                # Add the meter protocol to the list of attributes
                reading['message']['protocol'] = config['meters'][reading['meter_id']]['protocol']
                mqtt_client.publish(
                    topic=f'{config["mqtt"]["base_topic"]}/{reading["meter_id"]}/attributes',
                    payload=dumps(reading['message']),
                    qos=1,
                    retain=False
                )

            if config['general']['sleep_for'] > 0 and len(missing_readings) == 0:
                # We have our readings, so we can sleep
                if LOG_LEVEL >= 3:
                    logger.info('All readings received.')
                    logger.info('Sleeping for %d seconds...', config["general"]["sleep_for"])
                # Shutdown everything, but mqtt_client
                shutdown(rtlamr=rtlamr, rtltcp=rtltcp, mqtt_client=None)
                try:
                    sleep(int(config['general']['sleep_for']))
                except KeyboardInterrupt:
                    logger.critical('Interrupted by user.')
                    keep_reading = False
                    shutdown(rtlamr=rtlamr, rtltcp=rtltcp, mqtt_client=mqtt_client, base_topic=config['mqtt']['base_topic'])
                    break
                except Exception:
                    logger.critical('Term siganal received. Exiting...')
                    keep_reading = False
                    shutdown(rtlamr=rtlamr, rtltcp=rtltcp, mqtt_client=mqtt_client, base_topic=config['mqtt']['base_topic'])
                    break
                if LOG_LEVEL >= 3:
                    logger.info('Time to wake up!')
                break

    # Shutdown
    shutdown(rtlamr = rtlamr, rtltcp = rtltcp, mqtt_client = mqtt_client, base_topic=config['mqtt']['base_topic'])


if __name__ == '__main__':
    # Call main function
    main()
