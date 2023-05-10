#!/usr/bin/env python3

import os
import sys
import re
import json
import signal
import subprocess
import socket
import ssl
import warnings
from datetime import datetime
from json import dumps, loads
from json.decoder import JSONDecodeError
from random import randrange
from struct import pack
from time import sleep, time
from fcntl import ioctl
from stat import S_ISCHR
import yaml
import requests
import usb.core
import paho.mqtt.publish as publish

from paho.mqtt import MQTTException

## Running as Add-on?
running_as_addon = False
if os.getenv("SUPERVISOR_TOKEN") is not None:
    running_as_addon = True

# From:
# https://stackoverflow.com/questions/14626395/how-to-properly-convert-a-c-ioctl-call-to-a-python-fcntl-ioctl-call
def reset_usb_device(usbdev):
    if usbdev is not None and ':' in usbdev:
        busnum, devnum = usbdev.split(':')
        filename = "/dev/bus/usb/{:03d}/{:03d}".format(int(busnum), int(devnum))
        if os.path.exists(filename) and S_ISCHR(os.stat(filename).st_mode):
            log_message('Resetting USB device: {}'.format(filename))
            #define USBDEVFS_RESET             _IO('U', 20)
            USBDEVFS_RESET = ord('U') << (4*2) | 20
            fd = open(filename, "wb")
            if int(ioctl(fd, USBDEVFS_RESET, 0)) != 0:
                log_message('Error resetting USB device!!!')
            else:
                log_message('Reset sucessful.')
            fd.close()

def load_id_file(sdl_ids_file):
    device_ids = []
    with open(sdl_ids_file) as f:
        for line in f:
            li = line.strip()
            if re.match(r"(^(0[xX])?[A-Fa-f0-9]+:(0[xX])?[A-Fa-f0-9]+$)", li) is not None:
                device_ids.append(line.rstrip().lstrip().lower())
    return device_ids

# Find RTL SDR device
def find_rtl_sdr_devices():
    # Load the list of all supported device ids
    DEVICE_IDS = load_id_file('/var/lib/sdl_ids.txt')
    devices_found = {}
    index = -1
    for dev in usb.core.find(find_all = True):
        for known_dev in DEVICE_IDS:
            usb_id, usb_vendor = known_dev.split(':')
            if dev.idVendor == int(usb_id, 16) and dev.idProduct == int(usb_vendor, 16):
                index += 1
                devices_found[known_dev] = { 'bus_address': '{:03d}:{:03d}'.format(dev.bus, dev.address), 'index': index}
                log_message('RTL SDR Device {} found on USB port {:03d}:{:03d} - Index: {}'.format(known_dev, dev.bus, dev.address, index))
                break
    return devices_found

# I have been experiencing some problems with my Radio (geeting old, maybe?)
# and the number of messages fills up my HDD very quickly.

# Function to log messages to STDERR
def log_message(message):
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
    print('[{}] {}'.format(dt_string, message), file=sys.stderr)

# Environment variable to help with Travis tests
# Set it to True if is set to 'yes' or 'true', false otherwise

def list_intersection(a, b):
    """
    Find the first element in the intersection of two lists
    """
    result = list(set(a).intersection(set(b)))
    return result[0] if result else None

class MqttSender:
    def __init__(self, mqtt_config):
        log_message('Configured MQTT sender:')
        self.d = {}
        self.d['hostname'] = mqtt_config.get('host', 'localhost')
        self.d['port'] = int(mqtt_config.get('port', 1883))
        self.d['username'] = mqtt_config.get('user', None)
        self.d['password'] = mqtt_config.get('password', None)
        self.d['client_id'] = mqtt_config.get('client_id', 'rtlamr2mqtt')
        self.d['base_topic'] = mqtt_config.get('base_topic', 'rtlamr')
        self.d['availability_topic'] = '{}/status'.format(self.d['base_topic'])
        tls_enabled = mqtt_config.get('tls_enabled', False)
        tls_ca = mqtt_config.get('tls_ca', '/etc/ssl/certs/ca-certificates.crt')
        tls_cert = mqtt_config.get('tls_cert', None)
        cert_reqs = ssl.CERT_NONE if mqtt_config.get('tls_insecure', True) else ssl.CERT_REQUIRED
        tls_keyfile = mqtt_config.get('tls_keyfile', None)
        self.d['tls'] = None
        if tls_enabled:
            self.d['tls'] = { 'ca_certs': tls_ca, 'certfile': tls_cert, 'keyfile': tls_keyfile, 'cert_reqs': cert_reqs }
        self.__log_mqtt_params(**self.d)

    def __get_auth(self):
        if self.d['username'] and self.d['password']:
            return { 'username':self.d['username'], 'password': self.d['password'] }
        return None

    def publish(self, **kwargs):
        log_message('Sending message to MQTT:')
        self.__log_mqtt_params(**kwargs)
        topic = kwargs.get('topic')
        payload = kwargs.get('payload', None)
        qos = int(kwargs.get('qos', 0))
        retain = kwargs.get('retain', False)
        will = { 'topic': self.d['availability_topic'], 'payload': 'offline', 'qos': 1, 'retain': True }
        try:
            publish.single(
                topic=topic, payload=payload, qos=qos, retain=retain, hostname=self.d['hostname'], port=self.d['port'],
                client_id=self.d['client_id'], keepalive=60, will=will, auth=self.__get_auth(), tls=self.d['tls']
            )
        except MQTTException as e:
            log_message('MQTTException connecting to MQTT broker: {}'.format(e))
            return False
        except Exception as e:
            log_message('Unknown exception connecting to MQTT broker: {}'.format(e))
            return False
        return True

    def __log_mqtt_params(self, **kwargs):
        for k, v in ((k, v) for (k, v) in kwargs.items() if k not in ['password']):
            log_message(' > {} => {}'.format(k, v))


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
        if not running_in_listen_only_mode:
            if mqtt_sender:
                mqtt_sender.publish(topic=availability_topic, payload='offline', retain=True)
        # Graceful termination
        sys.exit(0)

def load_yaml_config(config_path):
    """
    Load config from Home Assistant Add-On.
    Args:
        config_path (str): Path to yaml config file
    """
    try:
        with open(config_path, 'r') as config_file:
            return yaml.safe_load(config_file)
    except FileNotFoundError:
        log_message('Configuration file cannot be found at "{}"'.format(config_path))
        sys.exit(-1)

def load_json_config(config_path):
    """Load config from Home Assistant Add-On"""

    current_config_file = os.path.join(config_path)
    return json.load(open(current_config_file))

def merge_defaults(defaults, tomerge):
    merged = {}
    for k in defaults.keys():
        if k in tomerge.keys():
            merged[k] = { **defaults[k], **tomerge[k] }
        else:
            merged[k] = { **defaults[k] }
    if 'meters' in tomerge:
        merged['meters'] = tomerge['meters']
    else:
        merged['meters'] = {}
    return merged

# Load and build default config
def load_config(argv):
    # Set default values:
    defaults = {
        'general': {
            'sleep_for': 0,
            'verbosity': 'info',
            'tickle_rtl_tcp': False,
            'device_id': 'single',
            'rtltcp_server': '127.0.0.1:1234',
        },
        'mqtt': {
            'host': None,
            'user': None,
            'password': None,
            'tls_enabled': False,
            'tls_ca': '/etc/ssl/certs/ca-certificates.crt',
            'tls_insecure': True,
            'ha_autodiscovery': True,
            'ha_autodiscovery_topic': 'homeassistant',
            'base_topic': 'rtlamr'
        },
        'custom_parameters': {
            'rtltcp': "-s 2048000",
            'rtlamr': "-unique=true",
        },
    }
    # Attempts to load config from json or yaml file
    # Use "/data/options.json" or "/etc/rtlamr2mqtt.yaml" as default config file
    if len(argv) != 2:
        for config_file in ["/data/options.json", "/etc/rtlamr2mqtt.yaml"]:
            if os.path.exists(config_file):
                config_path = config_file
                log_message('Using "{}" config file'.format(config_path))
                break
    else:
        # If called with argument, use it as configuration file
        config_path = argv[1]

    if config_path[-5:] == '.json' or config_path[-3:] == '.js':
        config = merge_defaults(defaults, load_json_config(config_path))
    elif config_path[-5:] == '.yaml' or config_path[-4:] == '.yml':
        config = merge_defaults(defaults, load_yaml_config(config_path))
    else:
        log_message('Config file format not supported.')
        sys.exit(-1)

    # Add meters to config
    if len(config['meters']) < 1 and not running_in_listen_only_mode:
        log_message('No Meter defined. Exiting...')
        sys.exit(-1)

    # Check for Supervisor
    if running_as_addon:
        if config['mqtt'].get('host', None) is None:
            api_url = "http://supervisor/services/mqtt"
            headers = {"Authorization": "Bearer " + os.getenv("SUPERVISOR_TOKEN")}
            log_message("Fetching default MQTT configuration from %s" % api_url)
            try:
                resp = requests.get(api_url, headers=headers)
                resp.raise_for_status()

                d = resp.json()['data']
                config['mqtt']['host'] = d.get('host')
                config['mqtt']['port'] = d.get('port')
                config['mqtt']['user'] = d.get('username', None)
                config['mqtt']['password'] = d.get('password', None)
                config['mqtt']['tls_enabled'] = d.get('ssl', False)
                if config['mqtt']['tls_enabled']:
                    config['mqtt']['tls_ca'] = '/etc/ssl/certs/ca-certificates.crt'
                    config['mqtt']['tls_insecure'] = True
            except Exception as e:
                log_message("Could not fetch default MQTT configuration: %s" % e)
        else:
            log_message('MQTT Host defined in config file. Ignoring Supervisor Configuration...')
    for arg in config['custom_parameters'].get('rtlamr', '').split():
        if '-server=' in arg:
            config['general']['rtltcp_server'] = arg.split('=')[1]
    return config

# This is a helper function to flag any error message from rtlamr
def is_an_error_message(message):
    if 'Error reading samples:' in message:
        return True
    return False

def format_number(number, format):
    return str(format.replace('#', '{}').format(*number.zfill(format.count('#'))))

def send_ha_autodiscovery(meter, mqtt_config):
    """
    Build and send HA Auto Discovery message for a meter
    """
    log_message('Sending MQTT autodiscovery payload to Home Assistant...')
    discover_topic = '{}/sensor/rtlamr/{}/config'.format(mqtt_config['ha_autodiscovery_topic'], meter['name'])
    discover_payload = {
        'name': meter['name'],
        'unique_id': str(meter['id']),
        'unit_of_measurement': meter['unit_of_measurement'],
        'icon': meter['icon'],
        'availability_topic': '{}/status'.format(mqtt_config['base_topic']),
        'force_update': True,
        'state_class': meter.get('state_class', 'total_increasing'),
        'state_topic': meter['state_topic'],
        'json_attributes_topic': meter['attribute_topic']
    }
    if meter['device_class'] is not None:
        discover_payload['device_class'] = meter['device_class']
    if meter['expire_after'] is not None:
        discover_payload['expire_after'] = meter['expire_after']
    mqtt_sender.publish(topic=discover_topic, payload=dumps(discover_payload), qos=1, retain=True)

def tickle_rtl_tcp(remote_server):
    """
    Connect to rtl_tcp and change some tuner settings. This has proven to
    reset some receivers that are blocked and producing errors.
    """
    SET_FREQUENCY = 0x01
    SET_SAMPLERATE = 0x02

    # extract host and port from remote_server string
    parts = remote_server.split(':', 1)
    remote_host = parts[0]
    remote_port = int(parts[1]) if parts[1:] else 1234
    log_message("Attempting to tune rtl_tcp to a different freq to shake things up")
    log_message("server: {}, host: {}, port: {}".format(remote_server, remote_host, remote_port))
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.settimeout(5) # 5 seconds
    send_cmd = lambda c, command, parameter: c.send(pack(">BI", int(command), int(parameter)))
    try:
        conn.connect((remote_host, remote_port))
        send_cmd(conn, SET_FREQUENCY, 88e6 + randrange(0, 20)*1e6) # random freq
        sleep(0.2)
        send_cmd(conn, SET_SAMPLERATE, 2048000)
        log_message("Successfully tickled rtl_tcp")
    except socket.error as err:
        log_message("Error connecting to rtl_tcp : {}".format(err))
    conn.close()

# Signal handlers/call back
signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

# LISTEN Mode
def listen_mode():
    log_message('Starting in LISTEN ONLY Mode...')
    msgtype = os.environ.get('RTL_MSGTYPE', 'all')
    rtlamr_cmd = ['/usr/bin/rtlamr', '-msgtype={}'.format(msgtype), '-format=json']
    external_rtl_tcp = False
    if running_as_addon:
        config = load_config(sys.argv)
        mqtt_sender = MqttSender(config['mqtt'])
        debug_topic = '{}/debug'.format(config['mqtt']['base_topic'])
        if re.match('127\.0\.0\.|localhost', config['general']['rtltcp_server']) is None:
            external_rtl_tcp = True
            log_message('Using an external RTL_TCP session at {}'.format(config['general']['rtltcp_server']))
            rtlamr_cmd.extend(['-server={}'.format(config['general']['rtltcp_server'])])
        del config
    else:
        log_message('No Supervisor detected.')
    '''
    If it exists, this reads the environment variable RTL_TCP_ARGS and appends it to rtl_tcp command line.
    For example, RTL-SDR index number 0:
    $ docker run -e LISTEN_ONLY=yes -e RTL_TCP_ARGS="-d 0" ...
    '''
    rtltcp_args = os.environ.get('RTL_TCP_ARGS', '')
    if 'nostart' in rtltcp_args:
        external_rtl_tcp = True
    if not external_rtl_tcp:
        external_rtl_tcp = False
        rtltcp_cmd = '/usr/bin/rtl_tcp {}'.format(rtltcp_args)
        log_message('Starting rtl_tcp with {}'.format(rtltcp_cmd))
        rtltcp = subprocess.Popen(rtltcp_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, universal_newlines=True)
        sleep(2)
    # Starting RTLAMR
    rtlamr_cmd.extend(os.environ.get('RTLAMR_ARGS', '').split())
    log_message('Starting rtlamr with ' + str(rtlamr_cmd))
    rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, universal_newlines=True)
    log_message('You should see all utility meters after this line:')
    # loop forever
    while True:
        for amrline in rtlamr.stdout:
            log_message(amrline[:-1])
            json_output = None
            if amrline[0] == '{':
                try:
                    json_output = loads(amrline)
                except JSONDecodeError:
                    json_output = None
            if json_output is not None and running_as_addon:
                mqtt_sender.publish(topic=debug_topic, payload=dumps(json_output), retain=False)

# Main
if __name__ == "__main__":

    running_in_listen_only_mode = False
    if str(os.environ.get('LISTEN_ONLY')).lower() in ['yes', 'true']:
        running_in_listen_only_mode = True

    if running_as_addon:
        config = load_config(sys.argv)
        running_in_listen_only_mode = config['general'].get('listen_only', False)

    if running_in_listen_only_mode:
        listen_mode()

    log_message('RTLAMR2MQTT Starting...')

    external_rtl_tcp = False
    if 'config' not in locals():
        config = load_config(sys.argv)

    # Is RTL_TCP external?
    if re.match('127\.0\.0\.|localhost', config['general']['rtltcp_server']) is None:
        external_rtl_tcp = True
        log_message('Using an external RTL_TCP session at {}'.format(config['general']['rtltcp_server']))

    if not external_rtl_tcp:
        # Find USB Devices
        usb_device_index = ''
        usb_devices = find_rtl_sdr_devices()
        if len(usb_devices) < 1:
            log_message('No RTL-SDR USB devices found. Exiting...')
            sys.exit(1)

        usb_device_id = str(config['general'].get('device_id', 'single')).lower()
        if re.match(r"(^(0[xX])?[A-Fa-f0-9]{4}:(0[xX])?[A-Fa-f0-9]{4}$)", usb_device_id) is not None:
            usb_device_index = '-d {}'.format(str(usb_devices[usb_device_id]['index']))
            usb_port = str(usb_devices[usb_device_id]['bus_address'])
        elif re.match(r"(^[0-9]{3}:([0-9]{3}$))", usb_device_id) is not None:
            log_message('Using USB port ID: {}'.format(usb_device_id))
            usb_port = usb_device_id
        else:
            log_message('No USB device specified in the config file, using the first found.')
            usb_device_id = list(usb_devices.keys())[0]
            usb_port = str(usb_devices[usb_device_id]['bus_address'])

        availability_topic = '{}/status'.format(config['mqtt']['base_topic'])

    meter_readings = {}
    # Build dict of meter configs
    meters = {}
    meter_names = set()
    protocols = []
    for meter in config['meters']:
        meter_id = str(meter['id']).strip()
        meter_name = str(meter.get('name', 'meter_{}'.format(meter_id)))

        if meter_id in meters or meter_name in meter_names:
            log_message('Error: Duplicate meter name ({}) or id ({}) found in config. Exiting.'.format(meter_name, meter_id))
            sys.exit(1)

        meters[meter_id] = meter.copy()
        meter_names.add(meter_name)
        meter_readings[meter_id] = 0

        meters[meter_id]['state_topic'] = '{}/{}/state'.format(config['mqtt']['base_topic'], meter_id)
        meters[meter_id]['attribute_topic'] = '{}/{}/attributes'.format(config['mqtt']['base_topic'], meter_id)
        meters[meter_id]['name'] = meter_name
        meters[meter_id]['unit_of_measurement'] = str(meter.get('unit_of_measurement', ''))
        meters[meter_id]['icon'] = str(meter.get('icon', 'mdi:gauge'))
        meters[meter_id]['device_class'] = str(meter.get('device_class', None))
        if meters[meter_id]['device_class'].lower() in ['none', 'null']:
            meters[meter_id]['device_class'] = None
        meters[meter_id]['expire_after'] = meter.get('expire_after', None)
        meters[meter_id]['sent_HA_discovery'] = False

        protocols.append(meter['protocol'])

    # Build RTLAMR and RTL_TCP commands
    rtltcp_custom = []
    rtlamr_custom = []
    if 'custom_parameters' in config:
        # Build RTLTCP command
        if 'rtltcp' in config['custom_parameters']:
            rtltcp_custom = config['custom_parameters']['rtltcp'].split(' ')
        # Build RTLAMR command
        if 'rtlamr' in config['custom_parameters']:
            rtlamr_custom = config['custom_parameters']['rtlamr'].split(' ')

    if not external_rtl_tcp:
        rtltcp_cmd = ['/usr/bin/rtl_tcp'] + [usb_device_index] + rtltcp_custom
    rtlamr_cmd = ['/usr/bin/rtlamr', '-msgtype={}'.format(','.join(protocols)), '-format=json', '-filterid={}'.format(','.join(meters.keys()))] + rtlamr_custom
    #################################################################

    # Main loop
    mqtt_sender = MqttSender(config['mqtt'])
    availability_topic = '{}/status'.format(config['mqtt']['base_topic'])
    while True:
        if not external_rtl_tcp:
            reset_usb_device(usb_port)

        mqtt_sender.publish(topic=availability_topic, payload='online', retain=True)

        # Is this the first time are we executing this loop? Or is rtltcp running?
        if not external_rtl_tcp and ('rtltcp' not in locals() or rtltcp.poll() is not None):
            log_message('Trying to start RTL_TCP: {}'.format(' '.join(rtltcp_cmd)))
            # start the rtl_tcp program
            rtltcp = subprocess.Popen(rtltcp_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, universal_newlines=True)
            log_message('RTL_TCP started with PID {}'.format(rtltcp.pid))
            # Wait until it is ready to receive connections
            try:
                outs, errs = rtltcp.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                outs = None
            log_message('RTL_TCP is ready to receive connections!')
            if outs is not None:
                log_message(outs)

        # Is this the first time are we executing this loop? Or is rtlamr running?
        if 'rtlamr' not in locals() or rtlamr.poll() is not None:
            if config['general']['tickle_rtl_tcp']:
                tickle_rtl_tcp(config['general']['rtltcp_server'])
            log_message('Trying to start RTLAMR: {}'.format(' '.join(rtlamr_cmd)))
            # start the rtlamr program.
            rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, universal_newlines=True)
            log_message('RTLAMR started with PID {}'.format(rtlamr.pid))

        # This is a counter to count the number of duplicate error messages
        error_count = 0
        for amrline in rtlamr.stdout:
            if not external_rtl_tcp and ('rtltcp' not in locals() or rtltcp.poll() is not None):
                try:
                    outs, errs = rtltcp.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    outs = None
                if outs is not None:
                    log_message('RTL_TCP: {}'.format(outs))
            if is_an_error_message(amrline):
                if error_count < 1:
                    log_message('Error reading samples from RTL_TCP.')
                error_count += 1
            # Error messages are flooding the Docker logs when an error happens
            # Try to not show everything but the necessary for debuging
            if config['general']['verbosity'] == 'debug' and not is_an_error_message(amrline):
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
                            formatted_reading = format_number(raw_reading, meters[meter_id]['format'])
                        else:
                            formatted_reading = str(raw_reading) # Nope, no formating, just the raw number

                        log_message('Meter "{}" - Consumption {}. Sending value to MQTT.'.format(meter_id, formatted_reading))

                        attributes = {}
                        if config['mqtt']['ha_autodiscovery']:
                            # if HA Autodiscovery is enabled, send the MQTT auto discovery payload once for each meter
                            if not meters[meter_id]['sent_HA_discovery']:
                                send_ha_autodiscovery(meters[meter_id], config['mqtt'])
                                meters[meter_id]['sent_HA_discovery'] = True
                        else:
                            msg_payload = formatted_reading

                        attributes['Message Type'] = json_output['Type']
                        attributes.update(json_output['Message'])
                        attribute_topic = meters[meter_id]['attribute_topic']
                        state_topic = meters[meter_id]['state_topic']
                        mqtt_sender.publish(topic=attribute_topic, payload=json.dumps(attributes), retain=True)
                        mqtt_sender.publish(topic=state_topic, payload=formatted_reading, retain=True)
                        meter_readings[meter_id] += 1

            if config['general']['sleep_for'] > 0: # We have a sleep_for parameter. Let's go to sleep!
                # Check if we have readings for all meters
                if all(list(meter_readings.values())):
                    # Set all meter readings values to 0
                    meter_readings = dict.fromkeys(meter_readings, 0)
                    # Exit from the main "for loop" and stop reading the rtlamr output
                    break

        # Kill all process
        log_message('Sleep_for defined, time to sleep!')
        log_message('Terminating all subprocess...')
        shutdown(0, 0)
        log_message('Sleeping for {} seconds, see you later...'.format(config['general']['sleep_for']))
        sleep(config['general']['sleep_for'])
