"""
Helper functions for building command for rtl_tcp and rtlamr
"""

import helpers.usb_utils as usbutils

def get_comma_separated_str(key, list_of_dict):
    """
    Get a comma-separated string of values for a given key from a list of dictionaries.
    """
    c = []
    for d in list_of_dict:
        if key in list_of_dict[d]:
            c.append(str(list_of_dict[d][key]))
    return ','.join(c)

def partial_match_remove(k, l):
    """
    Remove items from a list of dictionaries that partially match a key.
    Args:
        k (str): The key to check for partial matches.
        l (list): The list of dictionaries to check.
    Returns:
        l: The modified list of dictionaries.
    """
    for n in l:
        if k in n:
            l.remove(n)
    return l

def build_rtlamr_args(config):
    """
    Build the command line arguments for the rtlamr command.
    Args:
        config (dict): The configuration dictionary.
    Returns:
        list: The command line arguments.
    """
    # Build the command line arguments for the rtlamr command
    # based on the configuration file
    meters = config['meters']
    default_args = [ '-format=json' ]
    rtltcp_host = [ f'-server={config["general"]["rtltcp_host"]}' ]
    if 'rtlamr' in config['custom_parameters']:
        custom_parameters = [ config['custom_parameters']['rtlamr'] ]
        custom_parameters = partial_match_remove('server', custom_parameters)
    else:
        custom_parameters = [ '-unique=true' ]

    # Build a comma-separated string of meter IDs
    ids = ','.join(list(meters.keys()))
    filterid_arg = [ f'-filterid={ids}' ]

    # Build a comma-separated string of message types
    msgtypes = get_comma_separated_str('protocol', meters)
    msgtype_arg = [ f'-msgtype={msgtypes}' ]

    return default_args + rtltcp_host + custom_parameters + filterid_arg + msgtype_arg

def build_rtltcp_args(config):
    """
    Build the command line arguments for the rtl_tcp command.
    Args:
        config (dict): The configuration dictionary.
    Returns:
        list: The command line arguments.
    """
    # Build the command line arguments for the rtlamr command
    # based on the configuration file
    if config["general"]["rtltcp_host"].split(':')[0] not in [ '127.0.0.1', 'localhost' ]:
        return None
    custom_parameters = ''
    if 'rtltcp' in config['custom_parameters']:
        custom_parameters = config['custom_parameters']['rtltcp']
    device_id = config['general']['device_id']
    sdl_devices = usbutils.find_rtl_sdr_devices()
    dev_arg = '-d 0'
    if device_id != '0' and device_id in sdl_devices:
        dev_arg = f'-d {sdl_devices.index(device_id)}'
    return [ custom_parameters, dev_arg]
