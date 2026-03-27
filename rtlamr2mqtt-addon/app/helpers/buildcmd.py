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


def has_prefix(prefix, args_list):
    """
    Check if any item in args_list starts with prefix.
    """
    return any(arg.startswith(prefix) for arg in args_list)


def partial_match_remove(prefix, args_list):
    """
    Remove items from a list that start with the given prefix.
    Returns a new list (does not modify the original).
    """
    return [arg for arg in args_list if not arg.startswith(prefix)]


def build_rtlamr_args(config):
    """
    Build the command line arguments for the rtlamr command.
    Custom parameters can override defaults like -unique.
    """
    meters = config['meters']

    # Parse custom parameters first so we can check for overrides
    custom_args = []
    if 'rtlamr' in config['custom_parameters']:
        custom_args = config['custom_parameters']['rtlamr'].split()
        custom_args = partial_match_remove('-server', custom_args)

    args = ['-format=json']
    args.append(f'-server={config["general"]["rtltcp_host"]}')

    # Add -unique=true only if not overridden by custom parameters
    if not has_prefix('-unique', custom_args):
        args.append('-unique=true')

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
    Custom parameters can override defaults like -s (sample rate).
    Returns None if rtl_tcp host is remote.
    """
    host = config['general']['rtltcp_host'].split(':')[0]
    if host not in ['127.0.0.1', 'localhost']:
        return None

    # Parse custom parameters first so we can check for overrides
    custom_args = []
    if 'rtltcp' in config['custom_parameters']:
        custom = config['custom_parameters']['rtltcp']
        if custom:
            custom_args = custom.split()

    args = []

    # Add -s 2048000 only if not overridden by custom parameters
    if not has_prefix('-s', custom_args):
        args.extend(['-s', '2048000'])

    args.extend(custom_args)

    # Device index
    device_id = config['general']['device_id']
    args.extend(['-d', str(device_id)])

    return args
