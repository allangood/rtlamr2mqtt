### RTLAMR2MQTT
This project was created to send readings made by RTLAMR to a MQTT broker.
My user case is to integrate it with Home Assistant.

***UPDATE***
Two fields were deprecated from the configuration file and are not necessary anymore:
 - field_meterid
 - field_consumption

If you don't know your Meter ID or the protocol to listen, you can run the container in DEBUG mode to listen for everything.
### How to run the container in DEBUG Mode:
```
docker run --rm -ti -e DEBUG=yes --device=/dev/bus/usb:/dev/bus/usb allangood/rtlamr2mqtt
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

### Credits to:
Credits to:

https://github.com/bemasher/rtlamr

https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr
