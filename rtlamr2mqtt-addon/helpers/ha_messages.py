# https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery

discovery_topic = '<discovery_prefix>/<component>/[<node_id>/]<object_id>/config'
"""
discovery_topic = 'homeassistant/device/rtlamr/config'

<discovery_prefix>: The Discovery Prefix defaults to homeassistant and this prefix can be changed.
<component>: One of the supported MQTT integrations, e.g., binary_sensor, or device in case of a device discovery.
<node_id>: (Optional): ID of the node providing the topic, this is not used by Home Assistant but may be used to structure the MQTT topic. The ID of the node must only consist of characters from the character class [a-zA-Z0-9_-] (alphanumerics, underscore and hyphen).
<object_id>: The ID of the device. This is only to allow for separate topics for each device and is not used for the entity_id. The ID of the device must only consist of characters from the character class [a-zA-Z0-9_-] (alphanumerics, underscore and hyphen).
"""

device_discovery_tpl = {
    "dev": {
        "ids": "ea334450945afc",
        "name": "Kitchen",
        "mf": "Bla electronics",
        "mdl": "xya",
        "sw": "1.0",
        "sn": "ea334450945afc",
        "hw": "1.0rev2"
    },
    "o": {
        "name":"bla2mqtt",
        "sw": "2.1",
        "url": "https://bla2mqtt.example.com/support"
    },
    "cmps": {
        "some_unique_component_id1": {
        "p": "sensor",
        "device_class":"temperature",
        "unit_of_measurement":"°C",
        "value_template":"{{ value_json.temperature}}",
        "unique_id":"temp01ae_t"
        "state_topic":"homeassistant/sensor/sensorBedroom/state",
        },
        "some_unique_id2": {
        "p": "sensor",
        "device_class":"humidity",
        "unit_of_measurement":"%",
        "value_template":"{{ value_json.humidity}}",
        "unique_id":"temp01ae_h"
        }
    },
    "state_topic":"sensorBedroom/state",
    "qos": 2
    }