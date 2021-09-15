### RTLAMR2MQTT
[![Build Status](https://app.travis-ci.com/allangood/rtlamr2mqtt.svg?branch=main)](https://app.travis-ci.com/allangood/rtlamr2mqtt)

This project was created to send readings made by RTLAMR to a MQTT broker.
My user case is to integrate it with Home Assistant.

### Latest Updates
*2021-09-13:*
 - A new configuration parameter has been added: *verbosity*
 - Environment variable *DEBUG* has been renamed to *LISTEN_ONLY* to prevent confusion
 - Better error handling and output (still work in progress)


### How to run the container in LISTEN ALL METERS Mode:
If you don't know your Meter ID or the protocol to listen, you can run the container in DEBUG mode to listen for everything.

In this mode, rtlamr2mqtt will ***not read the configuration file***, this means that nothing is going to happen other than print all meter readings on screen!
```
docker run --rm -ti -e LISTEN_ONLY=yes -e RTL_MSGTYPE="scm+" --device=/dev/bus/usb:/dev/bus/usb allangood/rtlamr2mqtt
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
  verbosity: debug # debug or info

# (Required section)
mqtt:
  host: 192.168.1.1
  user: mqtt
  password: my very strong password
  ha_autodiscovery: true
  ha_autodiscovery_topic: homeassistant

# (Optional)
custom_parameters:
  rtltcp: "-s 2048000"
  # ***DO NOT ADD -msgtype, -filterid nor -protocol parameters here***
  rtlamr: "-unique=true -symbollength=7"

meters:
  - id: 7823010
    protocol: scm+
    name: meter_water
    format: "#####.###"
    unit_of_measurement: "\u33A5"
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


### Credits to:

https://github.com/bemasher/rtlamr

https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr
