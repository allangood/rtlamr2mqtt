### RTLAMR2MQTT
This project was created to send readings made by RTLAMR to a MQTT broker.
My user case is to integrate it with Home Assistant.

I didn't know anyone else was using this project, but I just got a request to extend it so expect a lot of changes in the upcoming days! :)

Home Assistant Utility:

![image](https://user-images.githubusercontent.com/757086/117556120-207bd200-b02b-11eb-9149-58eaf9c6c4ea.png)


Home Assistant configuration:
```
utility_meter:
  hourly_water:
    source: sensor.meter_<meter_id>
    cycle: hourly
  daily_water:
    source: sensor.meter_<meter_id>
    cycle: daily
  monthly_water:
    source: sensor.meter_<meter_id>
    cycle: monthly
```

Configuration sample:
```
mqtt:
  host: 192.168.1.1
  user: mqtt
  password: sdfhkjh(*&
  ha_autodiscovery: true
  ha_autodiscovery_topic: homeassistant

meters:
  - id: 7823010
    protocol: scm+
    name: meter_water
    field_meterid: 6
    field_consumption: 7
    format: #####.###
    unit_of_measurement: "\u33A5"
    icon: mdi:gauge
  - id: 6567984
    protocol: scm
    name: meter_water
    id_field: 2
    read_field: 3
    unit: kWh
```

Docker compose configuration:
```
version: "3"
services:
  rtlamr:
    container_name: rtlamr2mqtt
    image: allangood/rtlamr2mqtt
    restart: unless-stopped
    devices:
      - /dev/bus/usb/004/002
    volumes:
      /etc/rtlamr2mqtt.yaml:/etc/rtlamr2mqtt.yaml:ro
