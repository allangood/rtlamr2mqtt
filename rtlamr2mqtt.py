#!/usr/bin/env python3

import os
import sys
import yaml
import signal
import subprocess
from time import sleep
from json import dumps,loads
import paho.mqtt.client as mqtt

# uses signal to shutdown and hard kill opened processes and self
def shutdown(signum, frame):
    if rtltcp.returncode is None:
        rtltcp.terminate()
        try:
            rtltcp.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtltcp.kill()
            rtltcp.wait()
    if rtlamr.returncode is None:
        rtlamr.terminate()
        try:
            rtlamr.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtlamr.kill()
            rtlamr.wait()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

# DEBUG Mode
# The DEBUG mode will run RTLAMR collecting all
# signals and dump it to the stdout to make it easy
# to find meters IDs and signals
if str(os.environ.get('DEBUG')).lower() in ['yes', 'true']:
    print('Starting in DEBUG Mode...', file=sys.stderr)
    if os.environ.get('RTL_MSGTYPE') not None:
        msgtype = os.environ.get('DEBUG')
    else:
        msgtype = 'all'
    rtltcp_cmd = ['/usr/bin/rtl_tcp']
    rtltcp = subprocess.Popen(rtltcp_cmd, stderr=subprocess.DEVNULL)
    sleep(2)
    rtlamr_cmd = ['/usr/bin/rtlamr', '-msgtype={}'.format(msgtype), '-format=json']
    rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
    # loop forever
    while True:
        for amrline in rtlamr.stdout:
            print(amrline, file=sys.stderr)

##################### BUILD CONFIGURATION #####################
with open('/etc/rtlamr2mqtt.yaml','r') as config_file:
  config = yaml.safe_load(config_file)

# Build MQTT configuration
mqtt_host = "127.0.0.1" if 'host' not in config['mqtt'] else config['mqtt']['host']
mqtt_port = 1883 if 'port' not in config['mqtt'] else int(config['mqtt']['port'])
mqtt_user = "user" if 'user' not in config['mqtt'] else config['mqtt']['user']
mqtt_password = "secret" if 'password' not in config['mqtt'] else config['mqtt']['password']
ha_autodiscovery_topic = "homeassistant" if 'ha_autodiscovery_topic' not in config['mqtt'] else str(config['mqtt']['ha_autodiscovery_topic'])
ha_autodiscovery = False
if 'ha_autodiscovery' in config['mqtt']:
    if str(config['mqtt']['ha_autodiscovery']).lower() in ['true', 'yes']:
        ha_autodiscovery = True

state_topic = 'rtlamr/{}/state'
mqtt_client = mqtt.Client(client_id='rtlamr2mqtt')
mqtt_client.username_pw_set(username=mqtt_user, password=mqtt_password)

if 'general' in config:
    sleep_for = 0 if 'sleep_for' not in config['general'] else config['general']['sleep_for']
else:
    sleep_for = 0

# Build RTLAMR config
# TODO: Add a configuration section for rtlamr and rtl_tcp configuration parameters
protocols = []
meter_ids = []
meter_readings = {}
for idx,meter in enumerate(config['meters']):
    config['meters'][idx]['name'] = str('meter_{}'.format(meter['id'])) if 'name' not in meter else str(meter['name'])
    config['meters'][idx]['unit_of_measurement'] = '' if 'unit_of_measurement' not in meter else str(meter['unit_of_measurement'])
    config['meters'][idx]['icon'] = 'mdi:gauge' if 'icon' not in meter else str(meter['icon'])
    protocols.append(meter['protocol'])
    meter_ids.append(str(meter['id']))
    meter_readings[str(meter['id'])] = 0
    # if HA Autodiscovery is enabled, send the MQTT payload
    if ha_autodiscovery:
        print('Sending MQTT autodiscovery payload to Home Assistant...', file=sys.stderr)
        discover_topic = '{}/sensor/rtlamr/{}/config'.format(ha_autodiscovery_topic, config['meters'][idx]['name'])
        discover_payload = {
            "name": config['meters'][idx]['name'],
            "unit_of_measurement": config['meters'][idx]['unit_of_measurement'],
            "icon": config['meters'][idx]['icon'],
            "state_topic": state_topic.format(config['meters'][idx]['name'])
        }
        mqtt_client.connect(host=mqtt_host, port=mqtt_port)
        mqtt_client.publish(topic=discover_topic), payload=dumps(discover_payload), qos=0, retain=True)
        mqtt_client.disconnect()

rtlamr_custom = []
if 'custom_parameters' in config:
    if 'rtlamr' in config['custom_parameters']:
        rtlamr_custom = config['custom_parameters']['rtlamr'].split(' ')
rtlamr_cmd = ['/usr/bin/rtlamr', '-msgtype={}'.format(','.join(protocols)), '-format=json', '-filterid={}'.format(','.join(meter_ids))] + rtlamr_custom
#################################################################

# Build RTLTCP command
rtltcp_custom = []
if 'custom_parameters' in config:
    if 'rtltcp' in config['custom_parameters']:
        rtltcp_custom = config['custom_parameters']['rtltcp'].split(' ')
rtltcp_cmd = ['/usr/bin/rtl_tcp'] + rtltcp_custom
#################################################################

# Main loop
while True:
    # Is this the first time are we executing this loop? Or is rtltcp running?
    if 'rtltcp' not in locals() or rtltcp.poll() is not None:
        # start the rtl_tcp program
        rtltcp = subprocess.Popen(rtltcp_cmd, stderr=subprocess.DEVNULL)
        print('RTL_TCP started with PID {}'.format(rtltcp.pid), file=sys.stderr)
        # Wait 2 seconds to settle
        sleep(2)
    # Is this the first time are we executing this loop? Or is rtlamr running?
    if 'rtlamr' not in locals() or rtlamr.poll() is not None:
        # start the rtlamr program.
        rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
        print('RTLAMR started with PID {}'.format(rtlamr.pid), file=sys.stderr)
    for amrline in rtlamr.stdout:
        try:
            json_output = loads(amrline)
        except json.decoder.JSONDecodeError:
            json_output = None
        if json_output is not None and 'Message' in json_output:
            if 'EndpointID' in json_output['Message']:
                meter_id = str(json_output['Message']['EndpointID']).strip()
            elif 'ID' in json_output['Message']:
                meter_id = str(json_output['Message']['ID']).strip()
            else:
                meter_id = None
            if 'Consumption' in json_output['Message']:
                raw_reading = str(json_output['Message']['Consumption']).strip()
            else:
                raw_reading = None
            if meter_id is not None and raw_reading is not None:
                for meter in config['meters']: # We have a reading, but we don't know for which meter is it, let's check
                    if meter_id == str(meter['id']).strip():
                        if 'format' in meter:
                            formated_reading = meter['format'].replace('#','{}').format(*raw_reading.zfill(meter['format'].count('#')))
                        else:
                            formated_reading = raw_reading
                        print('Meter "{}" - Consumption {}. Sending value to MQTT.'.format(meter_id, formated_reading), file=sys.stderr)
                        mqtt_client.connect(host=mqtt_host, port=mqtt_port)
                        mqtt_client.publish(topic=state_topic.format(meter['name']), payload=str(formated_reading).encode('utf-8'), qos=0, retain=True)
                        mqtt_client.disconnect()
                        meter_readings[meter_id] += 1
        if sleep_for > 0:
            # Check if we have readings for all meters
            if len({k:v for (k,v) in meter_readings.items() if v > 0}) >= len(meter_readings):
                # Set all values to 0
                meter_readings = dict.fromkeys(meter_readings, 0)
                # Exit from the main for loop and stop reading the rtlamr output
                break
    # Kill all process
    if rtltcp.returncode is None:
        rtltcp.terminate()
        try:
            rtltcp.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtltcp.kill()
            rtltcp.wait()
    if rtlamr.returncode is None:
        rtlamr.terminate()
        try:
            rtlamr.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtlamr.kill()
            rtlamr.wait()
    sleep(sleep_for)
