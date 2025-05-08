import os
import helpers.usb_utils as usbutils

def get_comma_separated_str(key, list_of_dict):
    c = []
    for dict in list_of_dict:
        if key in dict:
            c.append(str(dict[key]))
    return ','.join(c)

def partial_match_remove(key, list):
    """
    Remove items from a list of dictionaries that partially match a key.
    Args:
        key (str): The key to check for partial matches.
        list (list): The list of dictionaries to check.
    Returns:
        list: The modified list of dictionaries.
    """
    for n in list:
        if '-server' in n:
            list.remove(n)
    return list

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
    args = []
    meters = config['meters']
    default_args = [ '-format=json' ]
    rtltcp_host = [ f'-server={config["general"]["rtltcp_host"]}' ]
    if 'rtlamr' in config['custom_parameters']:
        custom_parameters = [ config['custom_parameters']['rtlamr'] ]
    else:
        custom_parameters = [ '-unique=true' ]
    default_args = partial_match_remove('server', default_args)
    ids = get_comma_separated_str('id', meters)
    filterid_arg = [ f'-filterid={ids}' ]
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
    custom_parameters = ''
    if 'rtltcp' in config['custom_parameters']:
        custom_parameters = config['custom_parameters']['rtltcp']
    device_id = config['general']['device_id']
    sdl_devices = usbutils.find_rtl_sdr_devices()
    dev_arg = '-d 0'
    if device_id != '0' and device_id in sdl_devices:
        dev_arg = f'-d {sdl_devices.index(device_id)}'
    return [ custom_parameters, dev_arg]