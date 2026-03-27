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

    reading_component = {
        'platform': 'sensor',
        'name': 'Reading',
        'value_template': '{{ value_json.reading|float }}',
        'json_attributes_topic': f'{base_topic}/{meter_id}/attributes',
        'unique_id': f'{meter_id}_reading',
    }

    # Merge optional meter config keys into the reading component
    optional_keys = [
        'unit_of_measurement', 'icon', 'device_class',
        'state_class', 'expire_after', 'force_update',
    ]
    for key in optional_keys:
        if key in meter_config:
            reading_component[key] = meter_config[key]

    return {
        'device': {
            'identifiers': [f'meter_{meter_id}'],
            'name': meter_name,
            'manufacturer': meter_config.get('manufacturer', 'RTLAMR2MQTT'),
            'model': meter_config.get('model', 'Smart Meter'),
            'sw_version': '1.0',
            'serial_number': meter_id,
            'hw_version': '1.0',
        },
        'origin': {
            'name': '2mqtt',
            'sw_version': i.version(),
            'support_url': i.origin_url(),
        },
        'components': {
            f'{meter_id}_reading': reading_component,
            f'{meter_id}_lastseen': {
                'platform': 'sensor',
                'name': 'Last Seen',
                'device_class': 'timestamp',
                'value_template': '{{ value_json.lastseen }}',
                'unique_id': f'{meter_id}_lastseen',
            },
        },
        'state_topic': f'{base_topic}/{meter_id}/state',
        'availability_topic': f'{base_topic}/status',
        'qos': 1,
    }
