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
        "ids": "065c3b2845606ee0",
        "name": "RTLAMR",
        "mf": "Allan GooD",
        "mdl": "RTL-SDR AMR Reader",
        "sw": "2",
        "sn": "87c831e0dae533a5"
    },
    "o": {
        "name":"rtlamr2mqtt",
        "sw": "2025.5.1",
        "url": "https://github.com/allangood/rtlamr2mqtt"
    },
    "cmps": {
        "<meter_id>_reading": {
            "p": "sensor",
            "device_class":"<device_class>",
            "unit_of_measurement":"<unit_of_measurement>",
            "value_template":"{{ value_json.reading}}",
            "unique_id":"<meter_id>_reading",
            "state_topic":"homeassistant/sensor/<base_topic>/state"
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