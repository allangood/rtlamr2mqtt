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
    source: sensor.<meter_name>
    cycle: hourly
  daily_water:
    source: sensor.<meter_name>
    cycle: daily
  monthly_water:
    source: sensor.<meter_name>
    cycle: monthly
```

Configuration sample:
```
# (Optional section)
general:
  # Sleep for this amount of seconds after one successful of every meter
  sleep_for: 300

# (Required section)
mqtt:
  host: 192.168.1.1
  user: mqtt
  password: sdfhkjh(*&
  ha_autodiscovery: true
  ha_autodiscovery_topic: homeassistant

# (Optional)
custom_parameters:
  rtltcp: "-s 2048000"
  # (Optional) Add any custom parameter to RTLAMR.
  # ***DO NOT ADD -msgtype, -filterid nor -protocol parameters here***
  rtlamr: "-unique=true -symbollength=7"

meters:
  - id: 7823010
    protocol: scm+
    name: meter_water
    field_meterid: 6
    field_consumption: 7
    format: "#####.###"
    unit_of_measurement: "\u33A5"
    icon: mdi:gauge
  - id: 6567984
    protocol: scm
    name: meter_hydro
    field_meterid: 3
    field_consumption: 7
    unit_of_measurement: kWh
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
