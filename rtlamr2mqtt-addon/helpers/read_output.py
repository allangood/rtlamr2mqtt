from json import loads

def list_intersection(a, b):
    """
    Find the first element in the intersection of two lists
    """
    result = list(set(a).intersection(set(b)))
    return result[0] if result else None

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
    if is_json(output):
        return loads(output)