### RTLAMR2MQTT

![Docker Pulls](https://img.shields.io/docker/pulls/allangood/rtlamr2mqtt)
[![GitHub license](https://img.shields.io/github/license/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/stargazers)
![GitHub contributors](https://img.shields.io/github/contributors/allangood/rtlamr2mqtt)
[![GitHub issues](https://img.shields.io/github/issues/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/issues)

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fallangood%2Frtlamr2mqtt)

### Platforms:

[![AMD64](https://img.shields.io/badge/AMD64-Yes-greenb)](https://img.shields.io/badge/AMD64-Yes-greenb)
[![i386](https://img.shields.io/badge/i386-Yes-greenb)](https://img.shields.io/badge/i386-Yes-greenb)
[![AARCH64](https://img.shields.io/badge/AARCH64-Yes-greenb)](https://img.shields.io/badge/AARCH64-Yes-greenb)
[![ARMv7](https://img.shields.io/badge/ARMv7-Yes-greenb)](https://img.shields.io/badge/ARMv7-Yes-greenb)
[![ARMhf](https://img.shields.io/badge/ARMhf-Yes-greenb)](https://img.shields.io/badge/ARMhf-Yes-greenb)

RTLAMR2MQTT is a small Python program to read your utility meter such as water, gas and energy using an inexpensive USB RTL-SDR device and send these readings to a MQTT broker to be integrated with Home Assistant or NodeRed.

The project is currently under heavy development!

### Current features

- Custom parameters for `rtl_tcp` and `rtlamr` (`custom_parameters` config option)
- It can run `rtl_tcp` locally or use an external instance running somewhere else (`custom_parameters` config option)
- MQTT TLS support (`tls_enabled` config option)
- Reset USB port before open it (`device_id` config option)
- Send an "wake up" call to a remote RTL_TCP instance before connect to it (`tickle_rtl_tcp` config option)
- Format reading number. Some meters reports a flat number that should be formatted with decimals (`format` config option)
- Sleep after successful reading to avoid heating the CPU too much (`sleep_for` config option)
- Support multiple meters with one instance
- Run as an Addon for Home Assistant with Supervisor support and MQTT auto configuration
- Full sensor customization: `name`, `state_class`, `device_class`, `expire_after`, `icon` and `unit_of_measurement`

### Planned features

- Better "LISTEN_ONLY" mode (release 2.2.0)

### Noteworthy Updates

### 2022-05-17

- Bug fixes for remote rtl_tcp and usb_reset logic #123
- Code changes to load config file and merge defaults
- Added vscode files to test the Addon development (finally!)

### 2022-04-12

- **REMOVED PARAMETER** usb_reset
- **ADDED PARAMETER** device_id
- **DEPRECATED** Anomaly detection (looks like no one is using it and it's not very reliable)
- **Changed Dockerfile**: Much smaller docker container

### 2022-04-12

- New `tls_enabled` parameter to avoid confusions
- Some fixes for the Add-On regarding the TLS configuration

### 2022-04-04

- New TLS parameters to MQTT connection
- New parameter: USB_RESET to address problem mentioned on #98

# Readme starts here

### What do I need?

**1) You need a smart meter**
First and most important, you must have a "smart" water/gas/energy meter. You can find a list of compatible meters [here](https://github.com/bemasher/rtlamr/blob/master/meters.csv)

**2) You need an USB RTL-SDR device**
I am using this one: [NooElec NESDR Mini USB](https://www.amazon.ca/NooElec-NESDR-Mini-Compatible-Packages/dp/B009U7WZCA/ref=sr_1_1_sspa?crid=JGS4RV7RXGQQ&keywords=rtl-sdr)

**3) You need a MQTT broker** (Like [Mosquitto](https://mosquitto.org/) )

**4) [Home Assistant](https://www.home-assistant.io/)** is optional, but highly recommended, because it is awesome!

### How it looks like?

![image](https://user-images.githubusercontent.com/757086/117556120-207bd200-b02b-11eb-9149-58eaf9c6c4ea.png)

![image](https://user-images.githubusercontent.com/757086/169098091-bdd93660-daf5-4c8a-bde1-c4b66e7bdb87.png)

### How to run and configure?

#### Home Assistant Add-On:

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fallangood%2Frtlamr2mqtt)

[![Open your Home Assistant instance and show the dashboard of a Supervisor add-on.](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?repository_url=https%3A%2F%2Fgithub.com%2Fallangood%2Frtlamr2mqtt&addon=6713e36e_rtlamr2mqtt)

Manually:

- Navigate to your Add-Ons (Configuration > Add-ons, Backups, & Supervisor)
- Click the Add-On Store button
- Navigate to Repositories (3 dots in the top-right corner > Repositories)
- Add this repository (https://github.com/allangood/rtlamr2mqtt) and click 'Add'
- You should now see the 'rtlamr' Add-On at the bottom of your Add-On Store. Click to install and configure.

#### Docker or Docker-Compose

If you are not [running the add-on](https://www.home-assistant.io/common-tasks/os#installing-third-party-add-ons), you must write the **rtlamr2mqtt.yaml** configuration file.

#### Configuration file sample

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
  # This may help with a remote rtl_tcp server.
  tickle_rtl_tcp: false
  # (Optional) USB Device ID. Use lsusb to get the device ID
  # Use "single" (default) if you have only one device
  # device_id: 'single'
  device_id: '0bda:2838'

# MQTT configuration.
mqtt:
  # Whether to use Home Assistant auto-discovery feature or not
  ha_autodiscovery: true
  # Home Assistant auto-discovery topic
  ha_autodiscovery_topic: homeassistant
  # Base topic to send status and updates
  base_topic: rtlamr
  # By default, leaving host, port, user, and password unset will tell
  # rtlamr2mqtt to use the default home assistant mqtt settings for those
  # options. If needed, you can override these default settings:
  # MQTT host name or IP address.
  host: 192.168.1.1
  # MQTT port.
  port: 1883
  # TLS Enabled? (False by default)
  tls_enabled: false
  # TLS CA certificate (mandatory if tls_enabled = true)
  tls_ca: "/etc/ssl/certs/ca-certificates.crt"
  # TLS server certificate (optional)
  tls_cert: "/etc/ssl/my_server_cert.crt"
  # TLS self-signed certificate/insecure certificate (optional, default true)
  tls_insecure: true
  # MQTT user name if you have, remove if you don't use authentication
  user: mqtt
  # MQTT user password if you use one, remove if you don't use authentication
  password: my-very-strong-password

# (Optional)
# This entire section is optional.
# If you don't need any custom parameter, don't use it.
# ***DO NOT ADD -msgtype, -filterid nor -protocol parameters here***
# -d parameter is not necessary anymore if you use device_id
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
    # (optional) Make the Home Assistant sensor `unavailable` after this many seconds without a reading
    # Default is 0, which means the sensor will never be marked unavailable due to lack of readings.
    expire_after:
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
  --device /dev/bus/usb:/dev/bus/usb \
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

### Home Assistant utility meter configuration (sample):

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

#### Finding USB Device ID

Using lsusb to find USB Device ID:

```
$ lsusb
Bus 008 Device 001: ID 1d6b:0001 Linux Foundation 1.1 root hub
Bus 005 Device 002: ID 0bda:2838 Realtek Semiconductor Corp. RTL2838 DVB-T
Bus 005 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 007 Device 001: ID 1d6b:0001 Linux Foundation 1.1 root hub
```

Device ID => **0bda:2838**

#### Manual HA configuration (if ha_autodiscovery = false)

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

In this mode, rtlamr2mqtt will **_not read the configuration file_**, this means that nothing is going to happen other than print all meter readings on screen!

```
docker run --rm -ti -e LISTEN_ONLY=yes -e RTL_MSGTYPE="all" --device=/dev/bus/usb:/dev/bus/usb allangood/rtlamr2mqtt
```

If you have multiple RTL-SDRs and wish to start the LISTEN ALL METERS mode on a specific device ID (or use other custom RTL_TCP arguments), add the argument: `-e RTL_TCP_ARGS="-d <serial-number>"`. For example:

```
docker run --rm -ti -e LISTEN_ONLY=yes -e RTL_MSGTYPE="all" -e RTL_TCP_ARGS="-d 777" --device=/dev/bus/usb:/dev/bus/usb allangood/rtlamr2mqtt
```

**Important note**

If you are running the Add-On, then a MQTT topic will be created with the output and you will be able to check the output using Home Assistant.
The topic is: <base_topic>/debug

Open the MQTT setting and listen in the debug topic:
[![Open your Home Assistant instance and show your MQTT configuration panel.](https://my.home-assistant.io/badges/config_mqtt.svg)](https://my.home-assistant.io/redirect/config_mqtt/)

#### LISTEN ONLY MODE with remote RTL_TCP:

You will need to define 2 enviroment variables:

- `RTL_TCP_ARGS=nostart`
- `RTLAMR_ARGS=-server=a.b.c.d:1234`

If you are using the Add-on, then these parameters will be read from the configuration file.

### Thanks to

A big thank you to all kind [contributions](https://github.com/allangood/rtlamr2mqtt/graphs/contributors)!

### Credits to:

RTLAMR - https://github.com/bemasher/rtlamr

RTL_TCP - https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr

Icon by:
[Sound icons created by Plastic Donut - Flaticon]("https://www.flaticon.com/free-icons/sound")
