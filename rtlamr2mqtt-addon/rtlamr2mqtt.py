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
from subprocess import Popen, PIPE
# import paho.mqtt.client as mqtt
import helpers.config as cnf
import helpers.buildcmd as cmd
import helpers.mqtt_client as m

def on_message(client, userdata, message):
    if log_level >= 4:
        logger(f"Received message: {message.payload.decode()} on topic {message.topic}")

def start_rtltcp(config):
    rtltcp_args = cmd.build_rtltcp_args(config)
    if log_level >= 3:
        logger.info(f'Starting RTL_TCP using `rtl_tcp {" ".join(rtltcp_args)}`')
    rtltcp = Popen(["rtl_tcp"] + rtltcp_args, close_fds=True, stdout=PIPE)
    rtltcp_is_ready = False
    # Wait for rtl_tcp to be ready
    while not rtltcp_is_ready:
        # Read the output in chunks
        rtltcp_output = rtltcp.stdout.read1().decode("utf-8")
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
    return rtlamr

def main():
    """
    Main function
    """
    # Load the configuration file
    config_path = os.path.join(os.path.dirname(__file__), sys.argv[1])
    err, msg, config = cnf.load_config(config_path)
    if err != 'success':
        logger.critical(msg)
        sys.exit(1)
    # Configuration file loaded successfully

    # Use log_level as a global variable
    global log_level
    log_level = ['none', 'error', 'warning', 'info', 'debug'].index(config['general']['verbosity'])
    ###

    if log_level >= 3:
        logger.info(msg)
    ###
    # Start RTL_TCP
    rtltcp = start_rtltcp(config)
    # Start RTLAMR
    rtlamr = start_rtlamr(config)
    ###
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
    mqtt_client.connect()
    mqtt_client.loop_start()
    # Set Last Will and Testament
    mqtt_client.set_last_will(topic="home/lastwill", payload="Client disconnected unexpectedly", qos=1, retain=True)

    # Terminate RTLAMR
    rtlamr.terminate()
    try:
        outs, errs = rtlamr.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        rtlamr.kill()
        outs, errs = rtlamr.communicate()
    # Terminate RTL_TCP
    rtltcp.terminate()
    try:
        outs, errs = rtltcp.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        rtltcp.kill()
        outs, errs = rtltcp.communicate()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

if __name__ == "__main__":
    # Set up logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(format='[%(asctime)s] %(levelname)s:%(message)s', level=logging.DEBUG)
    log_level = 0
    # Call main function
    main()