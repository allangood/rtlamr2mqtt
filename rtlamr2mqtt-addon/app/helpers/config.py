"""
Helper functions for loading configuration files
"""

import os
import requests
from json import load
from yaml import safe_load


def get_mqtt_info_from_supervisor(mqtt_config):
    """
    Get MQTT broker information from the Supervisor API.
    """
    token = os.getenv("SUPERVISOR_TOKEN")
    if token is None:
        return mqtt_config

    api_url = 'http://supervisor/services/mqtt'
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()['data']
        mqtt_config['host'] = data.get('host')
        mqtt_config['port'] = data.get('port')
        mqtt_config['user'] = data.get('username', None)
        mqtt_config['password'] = data.get('password', None)
        mqtt_config['tls_enabled'] = data.get('ssl', False)
    except Exception:
        return mqtt_config

    return mqtt_config


def load_config(config_path=None):
    """
    Load the configuration file.
    Returns a tuple of (status, message, config_dict).
    """
    # Search for config file in default locations if no path given
    search_paths = [
        '/data/options.json',
        '/data/options.js',
        '/data/options.yaml',
        '/data/options.yml',
        '/etc/rtlamr2mqtt.yaml',
    ]
    if config_path is None:
        for path in search_paths:
            if os.path.isfile(path) and os.access(path, os.R_OK):
                config_path = path
                break
    if config_path is None:
        return ('error', 'No config file found.', None)

    if not os.path.isfile(config_path):
        return ('error', 'Config file not found.', None)
    if not os.access(config_path, os.R_OK):
        return ('error', 'Config file not readable.', None)

    file_extension = os.path.splitext(config_path)[1]
    if file_extension in ['.json', '.js']:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = load(file)
    elif file_extension in ['.yaml', '.yml']:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = safe_load(file)
    else:
        return ('error', 'Config file format not supported.', None)

    if 'meters' not in config:
        return ('error', 'No meters section found in config file.', None)

    # Parse sections with defaults
    general = config.get('general') or {}
    mqtt = config.get('mqtt') or {}
    custom_parameters = config.get('custom_parameters') or {}

    # General section
    general['sleep_for'] = int(general.get('sleep_for', 0))
    general['verbosity'] = str(general.get('verbosity', 'info'))
    general['device_id'] = int(general.get('device_id', 0))
    general['rtltcp_host'] = str(general.get('rtltcp_host', '127.0.0.1:1234'))

    # MQTT section
    mqtt['host'] = mqtt.get('host', None)
    if mqtt['host'] is None:
        mqtt = get_mqtt_info_from_supervisor(mqtt)
    else:
        mqtt['port'] = int(mqtt.get('port', 1883))
        mqtt['user'] = mqtt.get('user', None)
        mqtt['password'] = mqtt.get('password', None)
        mqtt['tls_enabled'] = bool(mqtt.get('tls_enabled', False))
    if mqtt.get('host') is None:
        return ('error', 'No MQTT broker information found.', None)
    mqtt['tls_insecure'] = bool(mqtt.get('tls_insecure', False))
    mqtt['tls_ca'] = mqtt.get('tls_ca', None)
    mqtt['tls_cert'] = mqtt.get('tls_cert', None)
    mqtt['tls_keyfile'] = mqtt.get('tls_keyfile', None)
    mqtt['base_topic'] = str(mqtt.get('base_topic', 'rtlamr'))
    mqtt['ha_status_topic'] = str(mqtt.get('ha_status_topic', 'homeassistant/status'))
    mqtt['ha_autodiscovery_topic'] = mqtt.get('ha_autodiscovery_topic', 'homeassistant')

    # Custom parameters section (defaults like -s 2048000 and -unique=true
    # are applied in buildcmd.py only when not overridden here)
    custom_parameters['rtltcp'] = str(custom_parameters.get('rtltcp', ''))
    custom_parameters['rtlamr'] = str(custom_parameters.get('rtlamr', ''))

    # Convert meters list to dict keyed by ID
    meters = {}
    meters_allowed_keys = [
        'id', 'protocol', 'name', 'format', 'unit_of_measurement',
        'icon', 'device_class', 'state_class', 'expire_after',
        'force_update', 'manufacturer', 'model',
    ]
    for m in config['meters']:
        m['state_class'] = m.get('state_class', 'total_increasing')
        meters[str(m['id'])] = {key: value for key, value in m.items() if key in meters_allowed_keys}

    return ('success', 'Config loaded successfully', {
        'general': general,
        'mqtt': mqtt,
        'custom_parameters': custom_parameters,
        'meters': meters,
    })
