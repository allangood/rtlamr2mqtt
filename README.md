
### RTLAMR2MQTT
[![Build Status](https://app.travis-ci.com/allangood/rtlamr2mqtt.svg?branch=main)](https://app.travis-ci.com/allangood/rtlamr2mqtt)
[![Docker Pulls](https://img.shields.io/docker/pulls/allangood/rtlamr2mqtt)](https://hub.docker.com/r/allangood/rtlamr2mqtt)

This project was created to send readings made by RTLAMR + RTL_TCP to a MQTT broker.
My user case is to integrate it with Home Assistant.

### Noteworthy Updates
*2022-01-11*
 - Happy new year! :)
 - Added "tickle_rtl_tcp" parameter to enable/disable the feature (explained below)
 - Added date/time to the log output
 - Added device_class configuration option #66 (thanks to @phidauex)
 - Some clean up in the README file!
 - Machine Learning to detect leaks still experimental and needs a lot of love to work properly

*2021-12-01*
 - Lots of changes!!!!
 - Using Debian bullseye instead of Alpine. Here is why: https://pythonspeed.com/articles/alpine-docker-python/
 - Added Machine Learn (Linear Regression) to detect potential leaks in the meter usage/readings (WiP)
   - This is still experimental. When I have it stabilized a new binary_sensor for every meter will be created to expose this information
   - A new attribute "Anomaly" is available for every meter. It will return "true" if an anomaly is detected.
   - ***IMPORTANT*** A new volume is necessary if you want to keep your history! See the compose/docker run command for more info.

# Readme starts here

### What do I need?
 **1) You need a smart meter**
First and most important, you must have a "smart" water/gas/energy meter. You can find a list of compatible meters [here](https://github.com/bemasher/rtlamr/blob/master/meters.csv)

 **2) You need an USB RT-SDR device**
I am using this one: [NooElec NESDR Mini USB](https://www.amazon.ca/NooElec-NESDR-Mini-Compatible-Packages/dp/B009U7WZCA/ref=sr_1_1_sspa?crid=JGS4RV7RXGQQ&keywords=rtl-sdr)

**3) You need a MQTT broker** (Like Mosquitto)

**4) Home assistant is optional, but highly recommended, because it is awesome!**

### How it looks like?

![image](https://user-images.githubusercontent.com/757086/117556120-207bd200-b02b-11eb-9149-58eaf9c6c4ea.png)
### How to run and configure?
Docker and Docker-compose are the most indicated way.
If you are not [running the add-on[(https://www.home-assistant.io/common-tasks/os#installing-third-party-add-ons), you must write the **rtlamr2mqtt.yaml** configuration file.

Create the config file on `/opt/rtlamr2mqtt/rtlamr2mqtt.yaml` for instance.
The configuration must looks like this:
```
# -- Configuration file starts here --
# (Optional section)
general:
  # Sleep for this amount of seconds after one successful reading of every meter
  # This parameter is helpful to keep CPU usage low and the temperature low as well
  # Set this to 0 (default) to disable it
  sleep_for: 300
  # Set the verbosity level. It can be debug or info
  verbosity: debug
  # Enable/disable the tickle_rtl_tcp. This is used to "shake" rtl_tcp to wake it up.
  # For me, this started to cause the rtl_tcp to refuse connections and miss the readings.
  tickle_rtl_tcp: false

# MQTT configuration.
mqtt:
  # Whether to use Home Assistant auto-discovery feature or not
  ha_autodiscovery: true
  # Home Assistant auto-discovery topic
  ha_autodiscovery_topic: homeassistant

  # By default, leaving host, port, user, and password unset will tell
  # rtlamr2mqtt to use the default home assistant mqtt settings for those
  # options. If needed, you can override these default settings:
  # MQTT host name or IP address.
  host: 192.168.1.1
  # MQTT port.
  port: 1883
  # MQTT user name if you have, remove if you don't use authentication
  user: mqtt
  # MQTT user password if you use one, remove if you don't use authentication
  password: my-very-strong-password

# (Optional)
# This entire section is optional.
# If you don't need any custom parameter, don't use it.
# ***DO NOT ADD -msgtype, -filterid nor -protocol parameters here***
custom_parameters:
  # Documentation for rtl_tcp: https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr
  rtltcp: "-s 2048000"
  # Documentation for rtlamr: https://github.com/bemasher/rtlamr/wiki/Configuration
  # If you want to disable the local rtl_tcp and use an external/remote one, you must add "-server=remote-ip-address:port" to the rtlamr section below.
  rtlamr: "-unique=true -symbollength=32"

# (Required section)
# Here is the place to define your meters
meters:
    # The ID of your meter
  - id: 7823010
    # The protocol
    protocol: scm+
    # A nice name to show on your Home Assistant/Node Red
    name: meter_water
    # (optional) A number format to be used for your meter
    format: "#####.###"
    # (optional) A measurement unit to be used by Home Assistant
    # Typical values are ft³ and m³ (use the superscript) for water/gas meters
    # and kWh or Wh for electric meters
    unit_of_measurement: "\u33A5"
    # (optional) An icon to be used by Home Assistant
    icon: mdi:gauge
    # A device_class to define what the sensor is measuring for use in the Energy panel
    # Typical values are "gas" or "energy". Default is blank.
    device_class:
    # "total_increasing" for most meters, "total" for meters that might go
    # backwards (net energy meters). Defaults to "total_increasing" if unset.
    state_class:
  - id: 6567984
    protocol: scm
    name: meter_hydro
    unit_of_measurement: kWh
    device_class: energy
# -- End of configuration file --
```
#### Run with docker
If you want to run with docker alone, run this command:
```
docker run --name rtlamr2mqtt \
  -v /opt/rtlamr2mqtt/rtlamr2mqtt.yaml:/etc/rtlamr2mqtt.yaml \
  -v /opt/rtlamr2mqtt/data:/var/lib/rtlamr2mqtt \
  -d /dev/bus/usb:/dev/bus/usb \
  --restart unless-stopped \
  allangood/rtlamr2mqtt
```
#### Run with docker-compose
If you use docker-compose (recommended), add this to your compose file:
```
version: "3"
services:
  rtlamr:
    container_name: rtlamr2mqtt
    image: allangood/rtlamr2mqtt
    restart: unless-stopped
    devices:
      - /dev/bus/usb
    volumes:
      - /opt/rtlamr2mqtt/rtlamr2mqtt.yaml:/etc/rtlamr2mqtt.yaml:ro
      - /opt/rtlamr2mqtt/data:/var/lib/rtlamr2mqtt
```

### Home Assistant configuration:
To add your meters to Home Assistant, add a section like this:
```
utility_meter:
  hourly_water:
    source: sensor.<meter_name>
    cycle: hourly
  daily_water:
    source: sensor.<meter_name>
    cycle: daily
  monthly_water:
    source: sensor.<meter_name>
    cycle: monthly
```
If you have `ha_autodiscovery: false` in your configuration, you will need to manually add the sensors to your HA configuration.

This is a sample for a water meter using the configuration from the sample configuration file:
```
sensor:
  - platform: mqtt
    name: "My Utility Meter"
    state_topic: rtlamr/meter_water/state
    unit_of_measurement: "\u33A5"
```
You must change `meter_water` with the name you have configured in the configuration YAML file (below)

### I don't know my meters ID, what can I do?
**How to run the container in LISTEN ALL METERS Mode:**
If you don't know your Meter ID or the protocol to listen, you can run the container in DEBUG mode to listen for everything.

In this mode, rtlamr2mqtt will ***not read the configuration file***, this means that nothing is going to happen other than print all meter readings on screen!
```
docker run --rm -ti -e LISTEN_ONLY=yes -e RTL_MSGTYPE="all" --device=/dev/bus/usb:/dev/bus/usb allangood/rtlamr2mqtt
```

### Thanks to
A big thank you for all kind contributions! And a even bigger thanks to these kind contributors:
- [AnthonyPluth](https://github.com/AnthonyPluth)
- [jonbloom](https://github.com/jonbloom)
- [jeffeb3](https://github.com/jeffeb3)
- [irakhlin](https://github.com/irakhlin)
- [ericthomas](https://github.com/ericthomas)
- [b0naf1de](https://github.com/b0naf1de)

### Credits to:

RTLAMR - https://github.com/bemasher/rtlamr

RTL_TCP - https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr
