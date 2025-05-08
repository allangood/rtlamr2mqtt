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
import helpers.config as cnf
import helpers.buildcmd as cmd
import helpers.mqtt_client as m
import helpers.read_output as ro
import helpers.usb_utils as usbutil


def shutdown(rtlamr, rtltcp, mqtt_client):
    if log_level >= 3:
        logger.info("Shutting down...")
    # Terminate RTLAMR
    if log_level >= 3:
        logger.info("Terminating RTLAMR...")
    rtlamr.terminate()
    try:
        outs, errs = rtlamr.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        rtlamr.kill()
        outs, errs = rtlamr.communicate()
    if log_level >= 3:
        logger.info("RTLAMR Terminitaed.")
    # Terminate RTL_TCP
    if log_level >= 3:
        logger.info("Terminating RTL_TCP...")
    rtltcp.terminate()
    try:
        outs, errs = rtltcp.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        rtltcp.kill()
        outs, errs = rtltcp.communicate()
    if log_level >= 3:
        logger.info("RTL_TCP Terminitaed.")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    if log_level >= 3:
        logger.info("All done. Bye!")

def signal_handler(signum, frame):
    raise Exception(f"Signal {signum} received.")

def on_message(client, userdata, message):
    if log_level >= 3:
        logger.info(f"Received message: {message.payload.decode()} on topic {message.topic}")

def start_rtltcp(config):
    if config['general']['device_id'] == '0':
        usb_id = usbutil.find_rtl_sdr_devices()[0]
    else:
        usb_id = config['general']['device_id']
    if log_level >= 3:
        logger.debug(f'Reseting USB device {usb_id}')
    usbutil.reset_usb_device(usb_id)
    rtltcp_args = cmd.build_rtltcp_args(config)
    if log_level >= 3:
        logger.info(f'Starting RTL_TCP using `rtl_tcp {" ".join(rtltcp_args)}`')
    rtltcp = Popen(["rtl_tcp"] + rtltcp_args, close_fds=True, stdout=PIPE)
    rtltcp_is_ready = False
    # Wait for rtl_tcp to be ready
    while not rtltcp_is_ready:
        # Read the output in chunks
        try:
            rtltcp_output = rtltcp.stdout.read1().decode("utf-8").strip('\n')
        except KeyboardInterrupt:
            logger.critical(f"Interrupted by user.")
            rtltcp_is_ready = False
            sys.exit(1)
        except Exception as e:
            logger.critical(e)
            rtltcp_is_ready = False
            sys.exit(1)
        if rtltcp_output:
            if log_level >= 4:
                logger.debug(rtltcp_output)
            if "listening..." in rtltcp_output:
                rtltcp_is_ready = True
                if log_level >= 3:
                    logger.info(f'RTL_TCP started!')
        # Check rtl_tcp status
        rtltcp.poll()
        if rtltcp.returncode is not None:
            logger.critical(f'RTL_TCP failed to start errcode: {rtltcp.returncode}')
            sys.exit(1)
    return rtltcp

def start_rtlamr(config):
    rtlamr_args = cmd.build_rtlamr_args(config)
    if log_level >= 3:
        logger.info(f'Starting RTLAMR using `rtlamr {" ".join(rtlamr_args)}`')
    rtlamr = Popen(["rtlamr"] + rtlamr_args, close_fds=True, stdout=PIPE)
    rtlamr_is_ready = False
    while not rtlamr_is_ready:
        try:
            rtlamr_output = rtlamr.stdout.read1().decode("utf-8").strip('\n')
        except KeyboardInterrupt:
            logger.critical(f"Interrupted by user.")
            rtlamr_is_ready = False
            sys.exit(1)
        except Exception as e:
            logger.critical(e)
            rtlamr_is_ready = False
            sys.exit(1)
        if rtlamr_output:
            if log_level >= 4:
                logger.debug(rtlamr_output)
            if 'set gain mode' in rtlamr_output:
                rtlamr_is_ready = True
                if log_level >= 3:
                    logger.info(f'RTLAMR started!')
        # Check rtl_tcp status
        rtlamr.poll()
        if rtlamr.returncode is not None:
            logger.critical(f'RTLAMR failed to start errcode: {rtlamr.returncode}')
            sys.exit(1)
    return rtlamr

def main():
    """
    Main function
    """
    # Load the configuration file
    config_path = os.path.join(os.path.dirname(__file__), sys.argv[1])
    err, msg, config = cnf.load_config(config_path)
    if err != 'success':
        # Error loading configuration file
        logger.critical(msg)
        sys.exit(1)
    # Configuration file loaded successfully
    # Use log_level as a global variable
    global log_level
    # Convert verbosity to a number and store as log_level
    log_level = ['none', 'error', 'warning', 'info', 'debug'].index(config['general']['verbosity'])
    if log_level >= 3:
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
        log_level=log_level,
        logger=logger,
    )
    mqtt_client.set_last_will(topic="home/lastwill", payload="Client disconnected unexpectedly", qos=1, retain=True)
    try:
        mqtt_client.connect()
    except Exception as e:
        logger.critical(f"Failed to connect to MQTT broker: {e}")
        sys.exit(1)
    ##################################################################
    mqtt_client.set_on_message_callback(on_message)
    mqtt_client.subscribe(config['mqtt']['ha_status_topic'], qos=1)
    # Set Last Will and Testament
    mqtt_client.loop_start()

    # Start RTL_TCP
    rtltcp = start_rtltcp(config)
    # Start RTLAMR
    rtlamr = start_rtlamr(config)
    # Signal handlers/call back
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    ##################################################################
    keep_reading = True
    while keep_reading:
        try:
            rtlamr_output = rtlamr.stdout.read1().decode("utf-8")
        except KeyboardInterrupt:
            logger.critical(f"Interrupted by user.")
            keep_reading = False
            break
        except Exception as e:
            logger.critical(e)
            keep_reading = False
            break
        if keep_reading and rtlamr_output:
            meter_id, consumption = None, None
            json_output = ro.read_rtlamr_output(rtlamr_output)
            if json_output is not None and 'Message' in json_output:
                meter_id_key = ro.list_intersection(json_output['Message'], ['EndpointID', 'ID', 'ERTSerialNumber'])
                if meter_id_key is not None:
                    meter_id = json_output['Message'][meter_id_key]
                consumption_key = ro.list_intersection(json_output['Message'], ['Consumption', 'LastConsumptionCount'])
                if consumption_key is not None:
                    consumption = json_output['Message'][consumption_key]
                if str(meter_id) in meter_ids_list:
                    if log_level >= 4:
                        logger.debug(f"Received message from ID {meter_id}: {json_output['Message']}")
                    # Publish the message to MQTT
                    mqtt_client.publish(
                        topic=f"{config['mqtt']['base_topic']}/{meter_id}",
                        payload=consumption,
                        qos=1,
                        retain=True,
                    )
                else:
                    if log_level >= 4:
                        logger.debug(f"Relevand Meter IDs not found in message: {json_output['Message']}")
    # Shutdown
    shutdown(rtlamr = rtlamr, rtltcp = rtltcp, mqtt_client = mqtt_client)


if __name__ == "__main__":
    # Set up logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.DEBUG)
    log_level = 0
    # Call main function
    main()