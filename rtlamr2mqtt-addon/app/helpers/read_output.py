"""
Helper functions for loading rtlamr output
"""

from json import loads


# Ordered by priority: most specific first
METER_ID_KEYS = ['EndpointID', 'ERTSerialNumber', 'ID']
CONSUMPTION_KEYS = ['Consumption', 'LastConsumptionCount', 'LastConsumption']


def first_matching_key(dictionary, keys):
    """
    Return the first key from `keys` that exists in `dictionary`, or None.
    """
    for key in keys:
        if key in dictionary:
            return key
    return None


def format_number(number, f):
    """
    Format a number according to a given format.
    """
    return str(f.replace('#', '{}').format(*str(number).zfill(f.count('#'))))


def is_json(test_string):
    """
    Check if a string is valid JSON
    """
    if not test_string:
        return False
    try:
        loads(test_string)
    except ValueError:
        return False
    return True


def read_rtlamr_output(output):
    """
    Read a line and check if it is valid JSON
    """
    if is_json(output):
        return loads(output)
    return None


def get_message_for_ids(rtlamr_output, meter_ids_list):
    """
    Search for meter IDs in the rtlamr output and return the first match.
    """
    json_output = read_rtlamr_output(rtlamr_output)
    if json_output is None or 'Message' not in json_output:
        return None

    message = json_output['Message']

    meter_id_key = first_matching_key(message, METER_ID_KEYS)
    if meter_id_key is None:
        return None

    meter_id = str(message[meter_id_key])
    if meter_id not in meter_ids_list:
        return None

    message.pop(meter_id_key)

    consumption_key = first_matching_key(message, CONSUMPTION_KEYS)
    if consumption_key is None:
        return None

    consumption = message.pop(consumption_key)
    return {'meter_id': meter_id, 'consumption': int(consumption), 'message': message}
