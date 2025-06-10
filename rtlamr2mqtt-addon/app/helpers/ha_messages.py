"""
Helper functions for writing MQTT payloads
"""

import helpers.info as i

def meter_discover_payload(base_topic, meter_config):
    """
    Returns the discovery payload for Home Assistant.
    """

    meter_id = meter_config.pop('id')
    meter_name = meter_config.get('name', 'Unknown Meter')
    meter_config.pop('name', None)

    template_payload = {
        "device": {
            "identifiers": f"meter_{meter_id}",
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
                "unit_of_measurement": meter_config['unit_of_measurement'],
                "icon": meter_config.get('icon', 'mdi:guage'),
                "device_class": meter_config['device_class'],
                "state_class": meter_config.get('state_class', 'total'),
                "expire_after": meter_config.get('expire_after', 0),
                "force_update": meter_config.get('force_update', True),
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

    template_payload['components'][f'{meter_id}_reading'].update(meter_config)

    return template_payload
