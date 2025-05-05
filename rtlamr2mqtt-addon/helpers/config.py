import os
from yaml import safe_load
from json import load, loads

def load_config(config_path):
    """
    Load the configuration file.
    """
    # Check if the file exists
    if not os.path.isfile(config_path):
        return ('error', 'Config file not found.', None)
    file_extension = os.path.splitext(config_path)[1]
    if file_extension in ['.json', '.js']:
        with open(config_path, 'r') as file:
            config = load(file)
    elif file_extension in ['.yaml', '.yml']:
        with open(config_path, 'r') as file:
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
    general['sleep_for'] = general.get('sleep_for', 0)
    general['verbosity'] = general.get('verbosity', 'info')
    general['device_id'] = general.get('device_id', '0')
    general['rtltcp_host'] = general.get('rtltcp_host', '127.0.0.1:1234')
    # MQTT section
    mqtt['host'] = mqtt.get('host', 'localhost')
    mqtt['port'] = mqtt.get('port', 1883)
    mqtt['user'] = mqtt.get('user', None)
    mqtt['password'] = mqtt.get('password', None)
    mqtt['base_topic'] = mqtt.get('base_topic', 'rtlamr')
    mqtt['tls_enabled'] = mqtt.get('tls_enabled', False)
    mqtt['tls_ca_cert'] = mqtt.get('tls_ca_cert', None)
    mqtt['tls_cert'] = mqtt.get('tls_cert', None)
    mqtt['tls_key'] = mqtt.get('tls_key', None)
    mqtt['tls_insecure'] = mqtt.get('tls_insecure', False)
    mqtt['ha_autodiscovery_topic'] = mqtt.get('ha_autodiscovery_topic', 'homeassistant')
    # Custom parameters section
    custom_parameters['rtltcp'] = custom_parameters.get('rtltcp', '-s 2048000')
    custom_parameters['rtlamr'] = custom_parameters.get('rtlamr', '-unique=true')
    # Build config
    config = {
        'general': general,
        'mqtt': mqtt,
        'custom_parameters': custom_parameters,
        'meters': config['meters'],
    }
    return ('success', 'Config loaded successfully', config)