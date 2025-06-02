"""
Helper functions for loading configuration files
"""

import os
from json import load
from yaml import safe_load

def load_config(config_path=None):
    """
    Load the configuration file.
    """
    # If no config path is provided, search for the config file in the default locations
    search_paths = [
        '/data/options.json',
        '/data/options.js',
        '/data/options.yaml',
        '/data/options.yml',
        '/etc/rtlamr2mqtt.yaml'
    ]
    if config_path is None:
        for path in search_paths:
            if os.path.isfile(path) and os.access(path, os.R_OK):
                config_path = path
                break
    if config_path is None:
        return ('error', 'No config file found.', None)
    ##############################################################

    # Check if the file exists and is readable
    if not os.path.isfile(config_path):
        return ('error', 'Config file not found.', None)
    if not os.access(config_path, os.R_OK):
        return ('error', 'Config file not readable.', None)

    # Get file extension
    file_extension = os.path.splitext(config_path)[1]
    if file_extension in ['.json', '.js']:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = load(file)
    elif file_extension in ['.yaml', '.yml']:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = safe_load(file)
    else:
        return ('error', 'Config file format not supported.', None)

    # Get values and set defauls
    general, mqtt, custom_parameters = {}, {}, {}
    if 'general' in config and config['general'] is not None:
        general = config['general']
    if 'mqtt' in config and config['mqtt'] is not None:
        mqtt = config['mqtt']
    if 'custom_parameters' in config and config['custom_parameters'] is not None:
        custom_parameters = config['custom_parameters']
    if 'meters' not in config:
        return ('error', 'No meters section found in config file.', None)
    # General section
    general['sleep_for'] = int(general.get('sleep_for', 0))
    general['verbosity'] = str(general.get('verbosity', 'info'))
    general['device_id'] = str(general.get('device_id', '0'))
    general['rtltcp_host'] = str(general.get('rtltcp_host', '127.0.0.1:1234'))
    # MQTT section
    mqtt['host'] = str(mqtt.get('host', 'localhost'))
    mqtt['port'] = int(mqtt.get('port', 1883))
    mqtt['user'] = mqtt.get('user', None)
    mqtt['password'] = mqtt.get('password', None)
    mqtt['tls_enabled'] = bool(mqtt.get('tls_enabled', False))
    mqtt['tls_insecure'] = bool(mqtt.get('tls_insecure', False))
    mqtt['tls_ca'] = mqtt.get('tls_ca', None)
    mqtt['tls_cert'] = mqtt.get('tls_cert', None)
    mqtt['tls_keyfile'] = mqtt.get('tls_keyfile', None)
    mqtt['base_topic'] = str(mqtt.get('base_topic', 'rtlamr'))
    mqtt['ha_status_topic'] = str(mqtt.get('ha_status_topic', 'homeassistant/status'))
    mqtt['ha_autodiscovery_topic'] = mqtt.get('ha_autodiscovery_topic', 'homeassistant')

    # Custom parameters section
    custom_parameters['rtltcp'] = str(custom_parameters.get('rtltcp', '-s 2048000'))
    custom_parameters['rtlamr'] = str(custom_parameters.get('rtlamr', '-unique=true'))

    # Convert meters to a dictionary with IDs as keys
    meters = {}
    meters_allowed_keys = [
        'id',
        'protocol',
        'name',
        'format',
        'unit_of_measurement',
        'icon',
        'device_class',
        'state_class',
        'expire_after',
        'force_update'
    ]
    for m in config['meters']:
        # Get only allowed keys and drop anything else
        meters[str(m['id'])] = { key: value for key, value in m.items() if key in meters_allowed_keys }

    # Build config
    config = {
        'general': general,
        'mqtt': mqtt,
        'custom_parameters': custom_parameters,
        'meters': meters,
    }
    return ('success', 'Config loaded successfully', config)
