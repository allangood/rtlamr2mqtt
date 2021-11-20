### RTLAMR2MQTT
[![Build Status](https://app.travis-ci.com/allangood/rtlamr2mqtt.svg?branch=main)](https://app.travis-ci.com/allangood/rtlamr2mqtt)
[![Docker Pulls](https://img.shields.io/docker/pulls/allangood/rtlamr2mqtt)](https://hub.docker.com/r/allangood/rtlamr2mqtt)

This project was created to send readings made by RTLAMR to a MQTT broker.
My user case is to integrate it with Home Assistant.

### Latest Updates
*2021-10-27*
 - Many fixes regarding error handling
 - More comments inside the code
 - Some code cleanup
 - Fix a bug for MQTT anonymous message publishing discovered by @jeffeb3
 - Using latest code for both rtl-sdr and rtamr in the Dockerfile

*2021-10-12*
 - The HA-ADDON is working now! A shout-out to @AnthonyPluth for his hard work!!! \o/
 - New feature to allow this container to run with a remote rtl_tcp. Thanks to @jonbloom
 - A bug was introduced by #28 and has been fixed.

*2021-09-23:*
 - New images are based on Alpine 3.14 *** IMPORTANT ***
   - If this container stops to work after you upgrade, please read this: [https://docs.linuxserver.io/faq](https://docs.linuxserver.io/faq)
 - We are working in a new image: HA-ADDON! Thanks to @AnthonyPluth ! Stay tuned for news about it!

*2021-09-13:*
 - A new configuration parameter has been added: *verbosity*
 - Environment variable *DEBUG* has been renamed to *LISTEN_ONLY* to prevent confusion
 - Better error handling and output (still work in progress)


### How to run the container in LISTEN ALL METERS Mode:
If you don't know your Meter ID or the protocol to listen, you can run the container in DEBUG mode to listen for everything.

In this mode, rtlamr2mqtt will ***not read the configuration file***, this means that nothing is going to happen other than print all meter readings on screen!
```
docker run --rm -ti -e LISTEN_ONLY=yes -e RTL_MSGTYPE="all" --device=/dev/bus/usb:/dev/bus/usb allangood/rtlamr2mqtt
```

### Home Assistant Utility:

![image](https://user-images.githubusercontent.com/757086/117556120-207bd200-b02b-11eb-9149-58eaf9c6c4ea.png)


### Home Assistant configuration:
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

This is a sample for a water meter using the configuration from the next section:
```
sensor:
  - platform: mqtt
    name: "My Utility Meter"
    state_topic: rtlamr/meter_water/state
    unit_of_measurement: "\u33A5"
```
You must change `meter_water` with the name you have configured in the configuration YAML file (below)


### Configuration sample:
```
# (Optional section)
general:
  # Sleep for this amount of seconds after one successful of every meter
  # Set this to 0 (default) to disable it
  sleep_for: 300
  # Set the verbosity level. It can be debug or info
  verbosity: debug

# (Required section)
# MQTT configuration
mqtt:
  # MQTT host name or IP address
  host: 192.168.1.1
  # MQTT user name if you have, remove if you don't use authentication
  user: mqtt
  # MQTT user password if you use one, remove if you don't use authentication
  password: my very strong password
  # Whether to use Home Assistant auto-discovery feature or not
  ha_autodiscovery: true
  # Home Assistant auto-discovery topic
  ha_autodiscovery_topic: homeassistant

# (Optional)
# This entire section is optional.
# If you don't need any custom parameter, don't use it.
# ***DO NOT ADD -msgtype, -filterid nor -protocol parameters here***
custom_parameters:
  # Documentation for rtl_tcp: https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr
  rtltcp: "-s 2048000"
  # Documentation for rtlamr: https://github.com/bemasher/rtlamr/wiki/Configuration
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
    # A number format to be used for your meter
    format: "#####.###"
    # A measurement unit to be used by Home Assistant
    unit_of_measurement: "\u33A5"
    # An icon to be used by Home Assistant
    icon: mdi:gauge
  - id: 6567984
    protocol: scm
    name: meter_hydro
    unit_of_measurement: kWh
```

### Docker compose configuration:
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
      - /etc/rtlamr2mqtt.yaml:/etc/rtlamr2mqtt.yaml:ro
```

### Thanks to
A big thank you for all kind contributions!
[AnthonyPluth](https://github.com/AnthonyPluth)
[jonbloom](https://github.com/jonbloom)
[jeffeb3](https://github.com/jeffeb3)
[irakhlin](https://github.com/irakhlin)
[ericthomas](https://github.com/ericthomas)
[b0naf1de](https://github.com/b0naf1de)

### Credits to:

https://github.com/bemasher/rtlamr

https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr
