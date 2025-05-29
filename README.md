### RTLAMR2MQTT

![Docker Pulls](https://img.shields.io/docker/pulls/allangood/rtlamr2mqtt)
[![GitHub license](https://img.shields.io/github/license/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/stargazers)
![GitHub contributors](https://img.shields.io/github/contributors/allangood/rtlamr2mqtt)
[![GitHub issues](https://img.shields.io/github/issues/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/issues)

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fallangood%2Frtlamr2mqtt)

### Platforms:

[![AMD64](https://img.shields.io/badge/AMD64-Yes-greenb)](https://img.shields.io/badge/AMD64-Yes-greenb)
[![AARCH64](https://img.shields.io/badge/AARCH64-Yes-greenb)](https://img.shields.io/badge/AARCH64-Yes-greenb)

RTLAMR2MQTT is a small Python program to read your utility meter such as water, gas and energy using an inexpensive USB RTL-SDR device and send these readings to a MQTT broker to be integrated with Home Assistant or NodeRed.

### Current features

- Custom parameters for `rtl_tcp` and `rtlamr` (`custom_parameters` config option)
- It can run `rtl_tcp` locally or use an external instance running somewhere else (`custom_parameters` config option)
- MQTT TLS support (`tls_enabled` config option)
- Reset USB port before open it (`device_id` config option)
- Format reading number. Some meters reports a flat number that should be formatted with decimals (`format` config option)
- Sleep after successful reading to avoid heating the CPU too much (`sleep_for` config option)
- Support multiple meters with one instance
- Run as an Addon for Home Assistant with Supervisor support and MQTT auto configuration
- Full sensor customization: `name`, `state_class`, `device_class`, `icon` and `unit_of_measurement`

### Planned features

- Function to find your meter ID based on your meter reading

### Noteworthy Updates

> [!CAUTION] > **Major code rewrite**
> After a long break without working on this project
> I am back with a major rewrite.
> The old code was too hard to maintain
> This is a completly new code.
> You old entities should be cleaned manually from your MQTT broker

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

#### Run with docker

If you want to run with docker alone, run this command:

```
docker run --name rtlamr2mqtt \
  -v /opt/rtlamr2mqtt/rtlamr2mqtt.yaml:/etc/rtlamr2mqtt.yaml \
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

#### Multiple RTL devices

If you have multiple RTL devices, you will need to specify the USB device you want to use

Using lsusb to find USB Device ID <BUS:Device>:

```
$ lsusb
Bus 008 Device 001: ID 1d6b:0001 Linux Foundation 1.1 root hub
Bus 005 Device 002: ID 0bda:2838 Realtek Semiconductor Corp. RTL2838 DVB-T <<< I want to use this device
Bus 005 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 002 Device 004: ID 0bda:2838 Realtek Semiconductor Corp. RTL2838 DVB-T
```

USB Device => **005:002**

### I don't know my meters ID, what can I do?

This is a planned feature...

### Thanks to

A big thank you to all kind [contributions](https://github.com/allangood/rtlamr2mqtt/graphs/contributors)!

### Credits to:

RTLAMR - https://github.com/bemasher/rtlamr

RTL_TCP - https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr

Icon by:
[Sound icons created by Plastic Donut - Flaticon]("https://www.flaticon.com/free-icons/sound")
