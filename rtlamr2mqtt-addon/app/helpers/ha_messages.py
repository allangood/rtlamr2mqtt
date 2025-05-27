"""
Helper functions for writing MQTT payloads
"""

import helpers.info as i

def meter_discover_payload(base_topic, meter_config):
    """
    Returns the discovery payload for Home Assistant.
    """

    meter_id = meter_config['id']
    meter_name = meter_config.get('name', 'Unknown Meter')
    device_class = meter_config.get('device_class', 'water')
    unit_of_measurement = meter_config.get('unit_of_measurement', 'm³')
    meter_icon = meter_config.get('icon', 'mdi:water')

    return {
        "device": {
            "identifiers": f"{device_class}_meter_{meter_id}",
            "name": meter_name,
            "manufacturer": "RTLAMR2MQTT",
            "model": "Smart Meter",
            "sw_version": "1.0",
            "serial_number": meter_id,
            "hw_version": "1.0"
        },
        "origin": {
            "name":"2mqtt",
            "sw_version": i.version(),
            "support_url": i.origin_url()
        },
        "components": {
            f"{meter_id}_reading": {
                "platform": "sensor",
                "name": "Reading",
                "device_class": device_class,
                "unit_of_measurement": unit_of_measurement,
                "icon": meter_icon,
                "value_template": "{{ value_json.reading|float }}",
                "json_attributes_topic": f"{base_topic}/{meter_id}/attributes",
                "unique_id": f"{meter_id}_reading"
            },
            f"{meter_id}_lastseen": {
                "platform": "sensor",
                "name": "Last Seen",
                "device_class": "date",
                "value_template":"{{ value_json.lastseen }}",
                "unique_id": f"{meter_id}_lastseen"
            }
        },
        "state_topic": f"{base_topic}/{meter_id}/state",
        "availability_topic": f"{base_topic}/status",
        "qos": 1
    }
