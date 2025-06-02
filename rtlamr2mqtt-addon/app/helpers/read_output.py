"""
Helper functions for loading rtlamr output
"""

from json import loads

def list_intersection(a, b):
    """
    Find the first element in the intersection of two lists
    """
    result = list(set(a).intersection(set(b)))
    return result[0] if result else None



def format_number(number, f):
    """
    Format a number according to a given format.
    """
    return str(f.replace('#', '{}').format(*str(number).zfill(f.count('#'))))



def is_json(test_string):
    """
    Check if a string is valid JSON
    """
    try:
        loads(test_string)
    except ValueError:
        return False
    return True



def read_rtlamr_output(output):
    """
    Read a line a check if it is valid JSON
    """
    if is_json(output):
        return loads(output)



def get_message_for_ids(rtlamr_output, meter_ids_list):
    """
    Search for meter IDs in the rtlamr output and return the first match.
    """
    meter_id, consumption = None, None
    json_output = read_rtlamr_output(rtlamr_output)
    if json_output is not None and 'Message' in json_output:
        message = json_output['Message']
        meter_id_key = list_intersection(message, ['EndpointID', 'ID', 'ERTSerialNumber'])
        if meter_id_key is not None:
            meter_id = str(message[meter_id_key])
            if meter_id in meter_ids_list:
                message.pop(meter_id_key)
                consumption_key = list_intersection(message, ['Consumption', 'LastConsumption', 'LastConsumptionCount'])
                if consumption_key is not None:
                    consumption = message[consumption_key]
                    message.pop(consumption_key)

        if meter_id is not None and consumption is not None:
            return { 'meter_id': str(meter_id), 'consumption': int(consumption), 'message': message }
    return None
