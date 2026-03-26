"""
Helper functions for building commands for rtl_tcp and rtlamr
"""


def get_comma_separated_str(key, meters_dict):
    """
    Get a comma-separated string of values for a given key from a meters dictionary.
    """
    values = []
    for meter_id in meters_dict:
        if key in meters_dict[meter_id]:
            values.append(str(meters_dict[meter_id][key]))
    return ','.join(values)


def partial_match_remove(prefix, args_list):
    """
    Remove items from a list that start with the given prefix.
    Returns a new list (does not modify the original).
    """
    return [arg for arg in args_list if not arg.startswith(prefix)]


def build_rtlamr_args(config):
    """
    Build the command line arguments for the rtlamr command.
    """
    meters = config['meters']

    args = ['-format=json']
    args.append(f'-server={config["general"]["rtltcp_host"]}')

    # Custom parameters (strip any -server= the user may have added)
    if 'rtlamr' in config['custom_parameters']:
        custom_args = config['custom_parameters']['rtlamr'].split()
        custom_args = partial_match_remove('-server', custom_args)
        args.extend(custom_args)

    # Meter IDs filter
    ids = ','.join(list(meters.keys()))
    args.append(f'-filterid={ids}')

    # Message types
    msgtypes = get_comma_separated_str('protocol', meters)
    args.append(f'-msgtype={msgtypes}')

    return args


def build_rtltcp_args(config):
    """
    Build the command line arguments for the rtl_tcp command.
    Returns None if rtl_tcp host is remote.
    """
    host = config['general']['rtltcp_host'].split(':')[0]
    if host not in ['127.0.0.1', 'localhost']:
        return None

    args = []

    # Custom parameters
    if 'rtltcp' in config['custom_parameters']:
        custom = config['custom_parameters']['rtltcp']
        if custom:
            args.append(custom)

    # Device index
    device_id = config['general']['device_id']
    args.append(f'-d {device_id}')

    return args
