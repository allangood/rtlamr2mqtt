#!/usr/bin/env python3

import json
import os
import sys
import yaml
import signal
import subprocess
import shutil
import paho.mqtt.publish as publish
from time import sleep
from json import dumps, loads
from paho.mqtt import MQTTException
from json.decoder import JSONDecodeError

# I have been experiencing some problems with my Radio (geeting old, maybe?)
# and the number of messages fills up my HDD very quickly.

# Function to log messages to STDERR
def log_message(message):
    print(message, file=sys.stderr)

# Environment variable to help with Travis tests
# Set it to True if is set to 'yes' or 'true', false otherwise
test_mode =  str(os.environ.get('TEST')).lower() in ['yes', 'true']
if test_mode:
    log_message('Running in test mode!')

def list_intersection(a, b):
    """
    Find the first element in the intersection of two lists
    """
    result = list(set(a).intersection(set(b)))
    return result[0] if result else None

class MqttSender:
    def __init__(self, hostname, port, username, password):
        log_message('Configured MQTT sender:')
        self.d = {}
        self.d['hostname'] = hostname if hostname else 'localhost'
        self.d['port'] = int(port) if port else 1883
        self.d['username'] = username
        self.d['password'] = password
        self.d['client_id'] = 'rtlamr2mqtt'
        self.__log_mqtt_params(**self.d)

    def __get_auth(self):
        if self.d['username'] and self.d['password']:
            return { 'username':self.d['username'], 'password': self.d['password'] }
        else:
            return None

    def publish(self, **kwargs):
        log_message('Sending message to MQTT:')
        self.__log_mqtt_params(**kwargs)
        topic = kwargs.get('topic')
        payload = kwargs.get('payload', None)
        qos = int(kwargs.get('qos', 0))
        retain = kwargs.get('retain', False)
        will = { 'topic': availability_topic, 'payload':'offline', 'qos': 1, 'retain': True }
        try:
            publish.single(
                topic=topic, payload=payload, qos=qos, retain=retain, hostname=self.d['hostname'], port=self.d['port'],
                client_id=self.d['client_id'], keepalive=60, will=will, auth=self.__get_auth(), tls=None
            )
        except MQTTException as e:
            log_message('MQTTException connecting to MQTT broker: {}'.format(e))
            return False
        except Exception as e:
            log_message('Unknown exception connecting to MQTT broker: {}'.format(e))
            return False
        return True

    def __log_mqtt_params(self, **kwargs):
        for k,v in ((k,v) for (k,v) in kwargs.items() if k not in ['password']):
            log_message(' > {} => {}'.format(k,v))


# uses signal to shutdown and hard kill opened processes and self
def shutdown(signum, frame):
    # When signum and frame == 0, it is me calling the function
    if signum == frame == 0:
        log_message('Kill process called.')
    else:
        log_message('Shutdown detected, killing process.')
    if not external_rtl_tcp and rtltcp.returncode is None:
        log_message('Killing RTL_TCP...')
        rtltcp.terminate()
        try:
            rtltcp.wait(timeout=5)
            log_message('Killed in the first attempt.')
        except subprocess.TimeoutExpired:
            rtltcp.kill()
            rtltcp.wait()
            log_message('Killed.')
    if rtlamr.returncode is None:
        log_message('Killing RTLAMR...')
        rtlamr.terminate()
        try:
            rtlamr.wait(timeout=5)
            log_message('Killed in the first attempt.')
        except subprocess.TimeoutExpired:
            rtlamr.kill()
            rtlamr.wait()
            log_message('Killed.')
    if signum != 0 and frame != 0:
        log_message('Graceful shutdown.')
        # Are we running in LISTEN_ONLY mode?
        if str(os.environ.get('LISTEN_ONLY')).lower() not in ['yes', 'true']:
            if mqtt_sender:
               mqtt_sender.publish(topic=availability_topic, payload='offline', retain=True)
        # Graceful termination
        sys.exit(0)

def load_config(argv):
    """
    Attempts to load config from json or yaml file
    """
    config_path = '/etc/rtlamr2mqtt.yaml' if len(argv) != 2 else argv[1]
    if config_path[-4] == 'json':
        return load_json_config()
    else:
        return load_yaml_config(config_path)

def load_yaml_config(config_path):
    """
    Load config from Home Assistant Add-On.
    Args:
        config_path (str): Path to yaml config file
    """
    try:
        with open(config_path,'r') as config_file:
            return yaml.safe_load(config_file)
    except FileNotFoundError:
        log_message('Configuration file cannot be found at "{}"'.format(config_path))
        sys.exit(-1)

def load_json_config():
    """Load config from Home Assistant Add-On"""

    current_config_file = os.path.join("/data/options.json")
    return json.load(open(current_config_file))

# This is a helper function to flag any error message from rtlamr
def is_an_error_message(message):
    if 'Error reading samples:' in message:
        return True
    else:
        return False

def send_ha_autodiscovery(meter, consumption_key):
    """
    Build and send HA Auto Discovery message for a meter
    """
    log_message('Sending MQTT autodiscovery payload to Home Assistant...')
    discover_topic = '{}/sensor/rtlamr/{}/config'.format(ha_autodiscovery_topic, meter['name'])
    divisor = 1 
    if 'format' in meter and '.' in meter['format']:
        """
        'format' parameter is in the form ######.### 
        Raise 10 to a power corresponding to the number of # characters in format 
        parameter that occur after the decimal. HA will divide the raw consumption 
        value by this amount.
        """
        divisor = 10 ** len((meter['format'].split('.',1))[1])
    discover_payload = {
        'name': meter['name'],
        'unique_id': str(meter['id']),
        'unit_of_measurement': meter['unit_of_measurement'],
        'icon': meter['icon'],
        'availability_topic': availability_topic,
        'state_class': 'total_increasing',
        'state_topic': meter['state_topic'],
        'value_template': '{{{{ value_json.Message.{} | float / {} }}}}'.format(consumption_key, divisor),
        'json_attributes_topic': meter['state_topic'],
        'json_attributes_template': '{{{{ value_json.Message | tojson }}}}'.format()
    }
    mqtt_sender.publish(topic=discover_topic, payload=dumps(discover_payload), qos=1, retain=True)

# Signal handlers/call back
signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

# LISTEN Mode
# The DEBUG mode will run RTLAMR collecting all
# signals and dump it to the stdout to make it easy
# to find meters IDs and signals.
# This mode WILL NOT read any configuration file
if str(os.environ.get('LISTEN_ONLY')).lower() in ['yes', 'true']:
    log_message('Starting in LISTEN ONLY Mode...')
    log_message('!!! IN THIS MODE I WILL NOT READ ANY CONFIGURATION FILE !!!')
    msgtype = os.environ.get('RTL_MSGTYPE', 'all')
    rtltcp_cmd = [shutil.which('rtl_tcp')]
    rtltcp = subprocess.Popen(rtltcp_cmd)
    sleep(2)
    rtlamr_cmd = [shutil.which('rtlamr'), '-msgtype={}'.format(msgtype), '-format=json']
    if test_mode:
        # Make sure the test will not hang forever during test
        rtlamr_cmd.append('-duration=2s')
    rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    # loop forever
    while True:
        for amrline in rtlamr.stdout:
            log_message(amrline)
        if test_mode:
            break

##################### BUILD CONFIGURATION #####################
config = load_config(sys.argv)

verbosity = str(config['general'].get('verbosity', 'info')).lower()
if 'general' in config:
    if test_mode:
        sleep_for = 0
    else:
        sleep_for = int(config['general'].get('sleep_for', 0))

# Build MQTT configuration
availability_topic = 'rtlamr/status'
params = []
for k in ['host', 'port', 'user', 'password']:
  params.append(config['mqtt'].get(k, None))
mqtt_sender = MqttSender(*params)

ha_autodiscovery_topic = config['mqtt'].get('ha_autodiscovery_topic', 'homeassistant')
ha_autodiscovery = False
if 'ha_autodiscovery' in config['mqtt']:
    if str(config['mqtt']['ha_autodiscovery']).lower() in ['true', 'yes']:
        ha_autodiscovery = True

# Build Meter and RTLAMR config and send HA Auto-discover payload if enabled
# TODO: Add a configuration section for rtlamr and rtl_tcp configuration parameters
protocols = []
meter_ids = []
meter_readings = {}
external_rtl_tcp = False

# Build dict of meter configs 
meters = {}
for idx,meter in enumerate(config['meters']):
    id = str(meter['id']).strip()
    meter_name = str(meter.get('name', 'meter_{}'.format(id)))
    for k in meters:
        if (meters[k]['name'] == meter_name) or (meters[k]['id'] == id):
            log_message('Error: Duplicate meter name ({}) or id ({}) found in config. Exiting.'.format(meter_name, id))
            sys.exit(1)

    meters[id] = meter.copy()
    meters[id]['state_topic'] = 'rtlamr/{}/state'.format(id)
    meters[id]['name'] = meter_name
    meters[id]['unit_of_measurement'] = str(meter.get('unit_of_measurement', ''))
    meters[id]['icon'] = str(meter.get('icon', 'mdi:gauge'))
    meters[id]['sent_HA_discovery'] = False
    protocols.append(meter['protocol'])
    meter_ids.append(id)
    meter_readings[id] = 0

# Build RTLAMR and RTL_TCP commands
rtltcp_custom = []
rtlamr_custom = []
if 'custom_parameters' in config:
    # Build RTLTCP command
    if 'rtltcp' in config['custom_parameters']:
        rtltcp_custom = config['custom_parameters']['rtltcp'].split(' ')
    # Build RTLAMR command
    if 'rtlamr' in config['custom_parameters']:
        if "-server" in config['custom_parameters']['rtlamr']:
            external_rtl_tcp = True
        rtlamr_custom = config['custom_parameters']['rtlamr'].split(' ')

rtltcp_cmd = [shutil.which('rtl_tcp')] + rtltcp_custom
rtlamr_cmd = [shutil.which('rtlamr'), '-msgtype={}'.format(','.join(protocols)), '-format=json', '-filterid={}'.format(','.join(meter_ids))] + rtlamr_custom
#################################################################

# Main loop
while True:
    mqtt_sender.publish(topic=availability_topic, payload='online', retain=True)

    # Is this the first time are we executing this loop? Or is rtltcp running?

    if not external_rtl_tcp and ('rtltcp' not in locals() or rtltcp.poll() is not None):
        log_message('Trying to start RTL_TCP: {}'.format(' '.join(rtltcp_cmd)))
        # start the rtl_tcp program
        rtltcp = subprocess.Popen(rtltcp_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, universal_newlines=True)
        log_message('RTL_TCP started with PID {}'.format(rtltcp.pid))
        # Wait until it is ready to receive connections
        for rtlline in rtltcp.stdout:
            log_message(rtlline.strip('\n'))
            if 'listening...' in rtlline:
                log_message('RTL_TCP is ready to receive connections!')
                break

    # Is this the first time are we executing this loop? Or is rtlamr running?
    if 'rtlamr' not in locals() or rtlamr.poll() is not None:
        log_message('Trying to start RTLAMR: {}'.format(' '.join(rtlamr_cmd)))
        # start the rtlamr program.
        rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, universal_newlines=True)
        log_message('RTLAMR started with PID {}'.format(rtlamr.pid))

    # This is a counter to count the number of duplicate error messages
    error_count = 0
    for amrline in rtlamr.stdout:
        if is_an_error_message(amrline):
            if error_count < 1:
                log_message('Error reading samples from RTL_TCP.')
            error_count += 1
        # Error messages are flooding the Docker logs when an error happens
        # Try to not show everything but the necessary for debuging
        if verbosity == 'debug' and not is_an_error_message(amrline):
            log_message(amrline.strip('\n'))

        # Check if the output line is a valid JSON output
        json_output = None
        if amrline[0] == '{':
            try:
                json_output = loads(amrline)
            except JSONDecodeError:
                json_output = None

        if json_output and 'Message' in json_output: # If it is a valid JSON and is not empty then...
            # Extract the Meter ID
            meter_id_key = list_intersection(json_output['Message'], ['EndpointID', 'ID', 'ERTSerialNumber'])
            meter_id = str(json_output['Message'][meter_id_key]).strip() if meter_id_key else None

            # Extract the consumption
            consumption_key = list_intersection(json_output['Message'], ['Consumption', 'LastConsumptionCount'])
            raw_reading = str(json_output['Message'][consumption_key]).strip() if consumption_key else None

            # If we could extract the Meter ID and the consumption, then...
            if meter_id and raw_reading:
                if meter_id in meters:
                     if 'format' in meters[meter_id]: # We have a "format" parameter, let's format the number!
                         formated_reading = str(meters[meter_id]['format'].replace('#','{}').format(*raw_reading.zfill(meters[meter_id]['format'].count('#'))))
                     else:
                         formated_reading = str(raw_reading) # Nope, no formating, just the raw number

                     log_message('Meter "{}" - Consumption {}. Sending value to MQTT.'.format(meter_id, formated_reading))
                     state_topic = 'rtlamr/{}/state'.format(meter_id)
                     if ha_autodiscovery:
                          # if HA Autodiscovery is enabled, send the MQTT auto discovery payload once for each meter
                          if not meters[meter_id]['sent_HA_discovery']:
                              send_ha_autodiscovery(meters[meter_id], consumption_key)
                              meters[meter_id]['sent_HA_discovery'] = True

                          msg_payload=json.dumps(json_output)
                     else:
                          msg_payload = formatted_reading

                     mqtt_sender.publish(topic=state_topic, payload=msg_payload, retain=True)
                     meter_readings[meter_id] += 1

        if sleep_for > 0 or test_mode: # We have a sleep_for parameter. Let's go to sleep!
            # Check if we have readings for all meters
            if all(list(meter_readings.values())):
                # Set all meter readings values to 0
                meter_readings = dict.fromkeys(meter_readings, 0)
                # Exit from the main "for loop" and stop reading the rtlamr output
                break

    # Kill all process
    log_message('Sleep_for defined, time to sleep!')
    log_message('Terminating all subprocess...')
    if not external_rtl_tcp and rtltcp.returncode is None:
        shutdown(0,0)
    if test_mode:
        # If in test mode and reached this point, everything is fine
        break
    log_message('Sleeping for {} seconds, see you later...'.format(sleep_for))
    sleep(sleep_for)
