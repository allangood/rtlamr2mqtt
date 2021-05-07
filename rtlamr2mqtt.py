#!/usr/bin/env python3

import os
import subprocess
import signal
import sys
from time import sleep
from json import dumps
import paho.mqtt.client as mqtt

# uses signal to shutdown and hard kill opened processes and self
def shutdown(signum, frame):
    rtltcp.send_signal(15)
    rtlamr.send_signal(15)
    sleep(1)
    rtltcp.send_signal(9)
    rtlamr.send_signal(9)
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

mqtt_host = "127.0.0.1" if os.environ.get('MQTT_HOST') is None else os.environ['MQTT_HOST']
mqtt_port = 1883 if os.environ.get('MQTT_PORT') is None else int(os.environ['MQTT_PORT'])
mqtt_user = "user" if os.environ.get('MQTT_USER') is None else os.environ['MQTT_USER']
mqtt_password = "secret" if os.environ.get('MQTT_PASSWORD') is None else os.environ['MQTT_PASSWORD']
rtlamr_protocol = "scm+" if os.environ.get('PROTOCOL') is None else os.environ['PROTOCOL']
meter_id = "" if os.environ.get('FILTER_ID') is None else os.environ['FILTER_ID']
sleep_for = 60 if os.environ.get('SLEEP') is None else float(os.environ['SLEEP'])

# start the rtl_tcp program
rtltcp = subprocess.Popen(["/usr/bin/rtl_tcp > /dev/null 2>&1 &"], shell=True,
    stdin=None, stdout=None, stderr=None, close_fds=True)

# Wait 5 seconds to settle
sleep(5)

mqtt_client = mqtt.Client(client_id='rtlamr2mqtt')
mqtt_client.username_pw_set(username=mqtt_user, password=mqtt_password)
mqtt_client.connect(host=mqtt_host, port=mqtt_port, keepalive=60)

state_topic = 'rtlamr/{}/state'.format(meter_id)
discover_topic = 'homeassistant/sensor/rtlamr/{}/config'.format(meter_id)
discover_payload = {"name": "meter_{}".format(meter_id), "unit_of_measurement": u"\u33A5", "icon": "mdi:gauge", "state_topic": state_topic}

mqtt_client.publish(topic=discover_topic, payload=dumps(discover_payload), qos=0, retain=True)

number_format = '{0:.3f}'
last_reading = 0.0
number_of_readings = 0

while True:
    # start the rtlamr program.
    rtlamr_cmd = ['/usr/bin/rtlamr', '-msgtype=%s' % rtlamr_protocol, '-format=csv', '-single=true', '-filterid={}'.format(meter_id)]
    rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for amrline in rtlamr.stdout:
        flds = amrline.strip('\n').split(',')
        if len(flds) > 8:
            print(flds, file=sys.stderr)
        try:
          reading = float("{}.{}".format(flds[7][:-3],flds[7][-3:]))
        except ValueError:
          reading = -1
          number_of_readings -= 1
        # Send a reading to MQTT after a good reading or after 10 readings (meter reset?)
        if reading >= last_reading or number_of_readings >= 10:
            mqtt_client.publish(topic=state_topic, payload=number_format.format(reading), qos=0, retain=False)
            last_reading = reading
            number_of_readings = 0
        else:
            number_of_readings += 1
    sleep(sleep_for)
