import pytest
import os

# Ensure helpers are importable from tests
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


@pytest.fixture
def sample_config():
    """A complete, valid configuration dict matching what config.load_config() returns."""
    return {
        'general': {
            'sleep_for': 0,
            'verbosity': 'info',
            'device_id': 0,
            'rtltcp_host': '127.0.0.1:1234',
        },
        'mqtt': {
            'host': '127.0.0.1',
            'port': 1883,
            'user': 'testuser',
            'password': 'testpass',
            'tls_enabled': False,
            'tls_insecure': False,
            'tls_ca': None,
            'tls_cert': None,
            'tls_keyfile': None,
            'base_topic': 'rtlamr',
            'ha_status_topic': 'homeassistant/status',
            'ha_autodiscovery_topic': 'homeassistant',
        },
        'custom_parameters': {
            'rtltcp': '',
            'rtlamr': '',
        },
        'meters': {
            '33333333': {
                'id': 33333333,
                'protocol': 'scm+',
                'name': 'my_water_meter',
                'format': '######.###',
                'unit_of_measurement': 'm³',
                'icon': 'mdi:gauge',
                'device_class': 'water',
                'state_class': 'total_increasing',
            },
            '22222222': {
                'id': 22222222,
                'protocol': 'r900',
                'name': 'my_energy_meter',
                'format': '######.###',
                'unit_of_measurement': 'KWh',
                'icon': 'mdi:gauge',
                'device_class': 'energy',
                'state_class': 'total_increasing',
            },
        },
    }


@pytest.fixture
def sample_rtlamr_scm_line():
    """A valid rtlamr SCM JSON output line for meter 33333333."""
    return '{"Time":"2025-05-05T21:25:11.959372062Z","Offset":0,"Length":0,"Type":"SCM","Message":{"ID":33333333,"Type":7,"TamperPhy":3,"TamperEnc":2,"Consumption":1978226,"ChecksumVal":60151}}'


@pytest.fixture
def sample_rtlamr_idm_line():
    """A valid rtlamr IDM JSON output line for meter 33333333."""
    return '{"Time":"2025-05-05T21:25:04.891578823Z","Offset":0,"Length":0,"Type":"IDM","Message":{"Preamble":1431639715,"PacketTypeID":28,"PacketLength":92,"HammingCode":198,"ApplicationVersion":4,"ERTType":7,"ERTSerialNumber":33333333,"ConsumptionIntervalCount":76,"ModuleProgrammingState":188,"TamperCounters":"AwIAcw4A","AsynchronousCounters":0,"PowerOutageFlags":"AAAAAAAA","LastConsumptionCount":1978208,"DifferentialConsumptionIntervals":[26,26,27,26,26,24,24,24,24,24,26,26,26,27,26,26,26,26,24,23,48,23,24,25,25,24,25,24,25,25,23,23,22,23,23,23,24,25,25,25,25,25,26,23,23,22,23],"TransmitTimeOffset":3911,"SerialNumberCRC":43319,"PacketCRC":49515}}'


@pytest.fixture
def sample_rtlamr_r900_line():
    """A valid rtlamr R900 JSON output line for meter 22222222 (not in default config but useful)."""
    return '{"Time":"2025-05-05T21:25:10.905527969Z","Offset":0,"Length":0,"Type":"R900","Message":{"ID":1111111111,"Unkn1":163,"NoUse":0,"BackFlow":0,"Consumption":4555831,"Unkn3":0,"Leak":2,"LeakNow":0}}'


@pytest.fixture
def mock_script_dir():
    """Path to the mock scripts directory."""
    return os.path.join(os.path.dirname(__file__), '..', 'mock')
