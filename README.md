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
    environment:
      - MQTT_USER=<MQTT_USER>
      - MQTT_PASSWORD=<MQTT_PASSWORD>
      - MQTT_HOST=<MQTT_HOST>
      - PROTOCOL=<protocol>
      - FILTER_ID=<meter_id>
      - SLEEP=<Sleep time in seconds>
```
