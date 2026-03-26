# Async Subprocess Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite rtlamr2mqtt from blocking subprocess management to a fully async architecture using asyncio, aiomqtt, and clean task separation.

**Architecture:** Three async tasks (meter_reader, mqtt_publisher, orchestrator) communicate via asyncio.Queue. External processes (rtl_tcp, rtlamr) are managed by a generic ManagedProcess class that handles start/ready-detection/retry/stop. MQTT uses aiomqtt for native async. Processes are killed during sleep to save resources on RPi.

**Tech Stack:** Python 3.13, asyncio, aiomqtt, paho-mqtt (transitive), pyyaml, pyusb, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-26-async-subprocess-refactor-design.md`

---

### Task 1: Project Setup — Dependencies and Test Infrastructure

**Files:**
- Modify: `rtlamr2mqtt-addon/requirements.txt`
- Create: `rtlamr2mqtt-addon/requirements-dev.txt`
- Create: `rtlamr2mqtt-addon/tests/conftest.py`
- Create: `rtlamr2mqtt-addon/pytest.ini`

- [ ] **Step 1: Update requirements.txt**

Replace the contents of `rtlamr2mqtt-addon/requirements.txt`:

```
aiomqtt>=2.0.0
paho-mqtt>=2.1.0
pyyaml==6.0.2
requests==2.32.4
pyusb==1.3.1
```

- [ ] **Step 2: Create requirements-dev.txt**

Create `rtlamr2mqtt-addon/requirements-dev.txt`:

```
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 3: Create pytest.ini**

Create `rtlamr2mqtt-addon/pytest.ini`:

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

- [ ] **Step 4: Create tests/conftest.py with shared fixtures**

Create `rtlamr2mqtt-addon/tests/conftest.py`:

```python
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
            'rtltcp': '-s 2048000',
            'rtlamr': '-unique=true',
        },
        'meters': {
            '33333333': {
                'id': 33333333,
                'protocol': 'scm+',
                'name': 'my_water_meter',
                'format': '######.###',
                'unit_of_measurement': 'm\u00b3',
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
```

- [ ] **Step 5: Install dev dependencies and verify pytest runs**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pip install -r requirements-dev.txt && pytest --co -q`

Expected: "no tests ran" (no test files yet), exit code 0 or 5 (no tests collected).

- [ ] **Step 6: Commit**

```bash
git add rtlamr2mqtt-addon/requirements.txt rtlamr2mqtt-addon/requirements-dev.txt rtlamr2mqtt-addon/pytest.ini rtlamr2mqtt-addon/tests/conftest.py
git commit -m "chore: set up test infrastructure and update dependencies"
```

---

### Task 2: Rewrite helpers/info.py and helpers/read_output.py (Pure Functions)

These have no I/O dependencies and are the simplest to test.

**Files:**
- Modify: `rtlamr2mqtt-addon/app/helpers/info.py` (no changes needed)
- Modify: `rtlamr2mqtt-addon/app/helpers/read_output.py`
- Create: `rtlamr2mqtt-addon/tests/test_read_output.py`

- [ ] **Step 1: Write failing tests for read_output**

Create `rtlamr2mqtt-addon/tests/test_read_output.py`:

```python
from helpers.read_output import is_json, format_number, read_rtlamr_output, get_message_for_ids


class TestIsJson:
    def test_valid_json(self):
        assert is_json('{"key": "value"}') is True

    def test_invalid_json(self):
        assert is_json('not json') is False

    def test_empty_string(self):
        assert is_json('') is False


class TestFormatNumber:
    def test_basic_format(self):
        assert format_number(1978226, '######.###') == '001978.226'

    def test_no_decimal(self):
        assert format_number(12345, '#####') == '12345'

    def test_zero_padded(self):
        assert format_number(42, '######.###') == '000000.042'


class TestReadRtlamrOutput:
    def test_valid_json_line(self, sample_rtlamr_scm_line):
        result = read_rtlamr_output(sample_rtlamr_scm_line)
        assert result is not None
        assert 'Message' in result
        assert result['Type'] == 'SCM'

    def test_invalid_json_line(self):
        result = read_rtlamr_output('not json at all')
        assert result is None

    def test_empty_string(self):
        result = read_rtlamr_output('')
        assert result is None


class TestGetMessageForIds:
    def test_scm_message_matching_id(self, sample_rtlamr_scm_line):
        result = get_message_for_ids(sample_rtlamr_scm_line, ['33333333'])
        assert result is not None
        assert result['meter_id'] == '33333333'
        assert result['consumption'] == 1978226
        assert isinstance(result['message'], dict)

    def test_idm_message_matching_id(self, sample_rtlamr_idm_line):
        result = get_message_for_ids(sample_rtlamr_idm_line, ['33333333'])
        assert result is not None
        assert result['meter_id'] == '33333333'
        assert result['consumption'] == 1978208

    def test_no_matching_id(self, sample_rtlamr_scm_line):
        result = get_message_for_ids(sample_rtlamr_scm_line, ['99999999'])
        assert result is None

    def test_empty_string(self):
        result = get_message_for_ids('', ['33333333'])
        assert result is None

    def test_non_json_string(self):
        result = get_message_for_ids('GainCount: 29', ['33333333'])
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_read_output.py -v`

Expected: Tests should pass already — the existing read_output.py code is correct (we are just adding test coverage). If any fail, investigate.

- [ ] **Step 3: Fix the non-deterministic ID key lookup in read_output.py**

Replace the `list_intersection` function and its usage in `rtlamr2mqtt-addon/app/helpers/read_output.py`. The current code uses `set()` intersection which has non-deterministic ordering. Replace with ordered lookup:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_read_output.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/helpers/read_output.py rtlamr2mqtt-addon/tests/test_read_output.py
git commit -m "refactor: fix non-deterministic key lookup in read_output, add tests"
```

---

### Task 3: Rewrite helpers/ha_messages.py

**Files:**
- Modify: `rtlamr2mqtt-addon/app/helpers/ha_messages.py`
- Create: `rtlamr2mqtt-addon/tests/test_ha_messages.py`

- [ ] **Step 1: Write failing tests for ha_messages**

Create `rtlamr2mqtt-addon/tests/test_ha_messages.py`:

```python
from helpers.ha_messages import meter_discover_payload
from helpers.info import version, origin_url


class TestMeterDiscoverPayload:
    def test_basic_structure(self, sample_config):
        meter_id = '33333333'
        meter_config = sample_config['meters'][meter_id]
        payload = meter_discover_payload('rtlamr', meter_config)

        assert 'device' in payload
        assert 'origin' in payload
        assert 'components' in payload
        assert 'state_topic' in payload
        assert 'availability_topic' in payload

    def test_device_info(self, sample_config):
        meter_config = sample_config['meters']['33333333']
        payload = meter_discover_payload('rtlamr', meter_config)

        device = payload['device']
        assert device['identifiers'] == 'meter_33333333'
        assert device['name'] == 'my_water_meter'
        assert device['serial_number'] == 33333333

    def test_origin(self, sample_config):
        meter_config = sample_config['meters']['33333333']
        payload = meter_discover_payload('rtlamr', meter_config)

        origin = payload['origin']
        assert origin['name'] == '2mqtt'
        assert origin['sw_version'] == version()
        assert origin['support_url'] == origin_url()

    def test_components_reading(self, sample_config):
        meter_config = sample_config['meters']['33333333']
        payload = meter_discover_payload('rtlamr', meter_config)

        reading = payload['components']['33333333_reading']
        assert reading['platform'] == 'sensor'
        assert reading['unique_id'] == '33333333_reading'
        assert reading['unit_of_measurement'] == 'm\u00b3'
        assert reading['device_class'] == 'water'

    def test_components_lastseen(self, sample_config):
        meter_config = sample_config['meters']['33333333']
        payload = meter_discover_payload('rtlamr', meter_config)

        lastseen = payload['components']['33333333_lastseen']
        assert lastseen['platform'] == 'sensor'
        assert lastseen['device_class'] == 'timestamp'
        assert lastseen['unique_id'] == '33333333_lastseen'

    def test_topics(self, sample_config):
        meter_config = sample_config['meters']['33333333']
        payload = meter_discover_payload('rtlamr', meter_config)

        assert payload['state_topic'] == 'rtlamr/33333333/state'
        assert payload['availability_topic'] == 'rtlamr/status'
        assert payload['qos'] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_ha_messages.py -v`

Expected: Some tests may fail due to the dead expression bug on line 15 and the `.update()` merging raw meter_config keys into the component.

- [ ] **Step 3: Rewrite ha_messages.py**

Replace `rtlamr2mqtt-addon/app/helpers/ha_messages.py`:

```python
"""
Helper functions for writing MQTT payloads
"""

import helpers.info as i


def meter_discover_payload(base_topic, meter_config):
    """
    Returns the discovery payload for Home Assistant.
    """
    meter_id = meter_config['id']
    meter_name = meter_config.get('name', 'Unknown Meter')

    reading_component = {
        'platform': 'sensor',
        'name': 'Reading',
        'value_template': '{{ value_json.reading|float }}',
        'json_attributes_topic': f'{base_topic}/{meter_id}/attributes',
        'unique_id': f'{meter_id}_reading',
    }

    # Merge optional meter config keys into the reading component
    optional_keys = [
        'unit_of_measurement', 'icon', 'device_class',
        'state_class', 'expire_after', 'force_update',
    ]
    for key in optional_keys:
        if key in meter_config:
            reading_component[key] = meter_config[key]

    return {
        'device': {
            'identifiers': f'meter_{meter_id}',
            'name': meter_name,
            'manufacturer': meter_config.get('manufacturer', 'RTLAMR2MQTT'),
            'model': meter_config.get('model', 'Smart Meter'),
            'sw_version': '1.0',
            'serial_number': meter_id,
            'hw_version': '1.0',
        },
        'origin': {
            'name': '2mqtt',
            'sw_version': i.version(),
            'support_url': i.origin_url(),
        },
        'components': {
            f'{meter_id}_reading': reading_component,
            f'{meter_id}_lastseen': {
                'platform': 'sensor',
                'name': 'Last Seen',
                'device_class': 'timestamp',
                'value_template': '{{ value_json.lastseen }}',
                'unique_id': f'{meter_id}_lastseen',
            },
        },
        'state_topic': f'{base_topic}/{meter_id}/state',
        'availability_topic': f'{base_topic}/status',
        'qos': 1,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_ha_messages.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/helpers/ha_messages.py rtlamr2mqtt-addon/tests/test_ha_messages.py
git commit -m "refactor: rewrite ha_messages with explicit key merging, fix dead expression bug"
```

---

### Task 4: Rewrite helpers/config.py

**Files:**
- Modify: `rtlamr2mqtt-addon/app/helpers/config.py`
- Create: `rtlamr2mqtt-addon/tests/test_config.py`

- [ ] **Step 1: Write failing tests for config**

Create `rtlamr2mqtt-addon/tests/test_config.py`:

```python
import os
import pytest
import tempfile
from helpers.config import load_config


def write_temp_yaml(content):
    """Write YAML content to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


MINIMAL_YAML = """
mqtt:
  host: 127.0.0.1
meters:
  - id: 12345678
    protocol: scm
    name: test_meter
    device_class: water
"""

FULL_YAML = """
general:
  sleep_for: 60
  verbosity: debug
  device_id: 1
  rtltcp_host: "192.168.1.100:1234"
mqtt:
  host: 10.0.0.1
  port: 8883
  user: mqttuser
  password: mqttpass
  tls_enabled: true
  tls_insecure: true
  tls_ca: /etc/ssl/ca.crt
  tls_cert: /etc/ssl/client.crt
  tls_keyfile: /etc/ssl/client.key
  base_topic: meters
  ha_status_topic: ha/status
  ha_autodiscovery_topic: ha
custom_parameters:
  rtltcp: "-s 1024000"
  rtlamr: "-unique=false"
meters:
  - id: 11111111
    protocol: r900
    name: gas_meter
    format: "#####.##"
    unit_of_measurement: ft3
    icon: mdi:fire
    device_class: gas
    state_class: total_increasing
"""


class TestLoadConfig:
    def test_minimal_config_defaults(self):
        path = write_temp_yaml(MINIMAL_YAML)
        try:
            status, msg, config = load_config(path)
            assert status == 'success'
            assert config['general']['sleep_for'] == 0
            assert config['general']['verbosity'] == 'info'
            assert config['general']['device_id'] == 0
            assert config['general']['rtltcp_host'] == '127.0.0.1:1234'
            assert config['mqtt']['port'] == 1883
            assert config['mqtt']['user'] is None
            assert config['mqtt']['tls_enabled'] is False
            assert config['mqtt']['base_topic'] == 'rtlamr'
            assert config['custom_parameters']['rtltcp'] == '-s 2048000'
            assert config['custom_parameters']['rtlamr'] == '-unique=true'
        finally:
            os.unlink(path)

    def test_full_config(self):
        path = write_temp_yaml(FULL_YAML)
        try:
            status, msg, config = load_config(path)
            assert status == 'success'
            assert config['general']['sleep_for'] == 60
            assert config['general']['verbosity'] == 'debug'
            assert config['general']['device_id'] == 1
            assert config['general']['rtltcp_host'] == '192.168.1.100:1234'
            assert config['mqtt']['host'] == '10.0.0.1'
            assert config['mqtt']['port'] == 8883
            assert config['mqtt']['tls_enabled'] is True
            assert config['mqtt']['base_topic'] == 'meters'
        finally:
            os.unlink(path)

    def test_meters_keyed_by_id(self):
        path = write_temp_yaml(MINIMAL_YAML)
        try:
            status, msg, config = load_config(path)
            assert '12345678' in config['meters']
            assert config['meters']['12345678']['name'] == 'test_meter'
            assert config['meters']['12345678']['state_class'] == 'total_increasing'
        finally:
            os.unlink(path)

    def test_missing_file(self):
        status, msg, config = load_config('/nonexistent/path.yaml')
        assert status == 'error'
        assert config is None

    def test_no_meters_section(self):
        path = write_temp_yaml("mqtt:\n  host: 127.0.0.1\n")
        try:
            status, msg, config = load_config(path)
            assert status == 'error'
        finally:
            os.unlink(path)

    def test_no_mqtt_host(self):
        content = "meters:\n  - id: 1\n    protocol: scm\n    name: m\n    device_class: water\n"
        path = write_temp_yaml(content)
        try:
            status, msg, config = load_config(path)
            # Without SUPERVISOR_TOKEN env var, this should fail
            assert status == 'error'
        finally:
            os.unlink(path)

    def test_device_id_as_integer(self):
        content = """
general:
  device_id: 2
mqtt:
  host: 127.0.0.1
meters:
  - id: 12345678
    protocol: scm
    name: test_meter
    device_class: water
"""
        path = write_temp_yaml(content)
        try:
            status, msg, config = load_config(path)
            assert status == 'success'
            assert config['general']['device_id'] == 2
            assert isinstance(config['general']['device_id'], int)
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_config.py -v`

Expected: `test_device_id_as_integer` will fail because current code does `str(general.get('device_id', '0'))`.

- [ ] **Step 3: Rewrite config.py with device_id as int**

Replace `rtlamr2mqtt-addon/app/helpers/config.py`:

```python
"""
Helper functions for loading configuration files
"""

import os
import requests
from json import load
from yaml import safe_load


def get_mqtt_info_from_supervisor(mqtt_config):
    """
    Get MQTT broker information from the Supervisor API.
    """
    token = os.getenv("SUPERVISOR_TOKEN")
    if token is None:
        return mqtt_config

    api_url = 'http://supervisor/services/mqtt'
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()['data']
        mqtt_config['host'] = data.get('host')
        mqtt_config['port'] = data.get('port')
        mqtt_config['user'] = data.get('username', None)
        mqtt_config['password'] = data.get('password', None)
        mqtt_config['tls_enabled'] = data.get('ssl', False)
    except Exception:
        return mqtt_config

    return mqtt_config


def load_config(config_path=None):
    """
    Load the configuration file.
    Returns a tuple of (status, message, config_dict).
    """
    # Search for config file in default locations if no path given
    search_paths = [
        '/data/options.json',
        '/data/options.js',
        '/data/options.yaml',
        '/data/options.yml',
        '/etc/rtlamr2mqtt.yaml',
    ]
    if config_path is None:
        for path in search_paths:
            if os.path.isfile(path) and os.access(path, os.R_OK):
                config_path = path
                break
    if config_path is None:
        return ('error', 'No config file found.', None)

    if not os.path.isfile(config_path):
        return ('error', 'Config file not found.', None)
    if not os.access(config_path, os.R_OK):
        return ('error', 'Config file not readable.', None)

    file_extension = os.path.splitext(config_path)[1]
    if file_extension in ['.json', '.js']:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = load(file)
    elif file_extension in ['.yaml', '.yml']:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = safe_load(file)
    else:
        return ('error', 'Config file format not supported.', None)

    if 'meters' not in config:
        return ('error', 'No meters section found in config file.', None)

    # Parse sections with defaults
    general = config.get('general') or {}
    mqtt = config.get('mqtt') or {}
    custom_parameters = config.get('custom_parameters') or {}

    # General section
    general['sleep_for'] = int(general.get('sleep_for', 0))
    general['verbosity'] = str(general.get('verbosity', 'info'))
    general['device_id'] = int(general.get('device_id', 0))
    general['rtltcp_host'] = str(general.get('rtltcp_host', '127.0.0.1:1234'))

    # MQTT section
    mqtt['host'] = mqtt.get('host', None)
    if mqtt['host'] is None:
        mqtt = get_mqtt_info_from_supervisor(mqtt)
    else:
        mqtt['port'] = int(mqtt.get('port', 1883))
        mqtt['user'] = mqtt.get('user', None)
        mqtt['password'] = mqtt.get('password', None)
        mqtt['tls_enabled'] = bool(mqtt.get('tls_enabled', False))
    if mqtt.get('host') is None:
        return ('error', 'No MQTT broker information found.', None)
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

    # Convert meters list to dict keyed by ID
    meters = {}
    meters_allowed_keys = [
        'id', 'protocol', 'name', 'format', 'unit_of_measurement',
        'icon', 'device_class', 'state_class', 'expire_after',
        'force_update', 'manufacturer', 'model',
    ]
    for m in config['meters']:
        m['state_class'] = m.get('state_class', 'total_increasing')
        meters[str(m['id'])] = {key: value for key, value in m.items() if key in meters_allowed_keys}

    return ('success', 'Config loaded successfully', {
        'general': general,
        'mqtt': mqtt,
        'custom_parameters': custom_parameters,
        'meters': meters,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_config.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/helpers/config.py rtlamr2mqtt-addon/tests/test_config.py
git commit -m "refactor: rewrite config.py, change device_id to integer index"
```

---

### Task 5: Rewrite helpers/buildcmd.py

**Files:**
- Modify: `rtlamr2mqtt-addon/app/helpers/buildcmd.py`
- Create: `rtlamr2mqtt-addon/tests/test_buildcmd.py`

- [ ] **Step 1: Write failing tests for buildcmd**

Create `rtlamr2mqtt-addon/tests/test_buildcmd.py`:

```python
from helpers.buildcmd import build_rtlamr_args, build_rtltcp_args


class TestBuildRtlamrArgs:
    def test_basic_args(self, sample_config):
        args = build_rtlamr_args(sample_config)
        assert '-format=json' in args
        assert '-server=127.0.0.1:1234' in args

    def test_filter_ids(self, sample_config):
        args = build_rtlamr_args(sample_config)
        filterid_args = [a for a in args if a.startswith('-filterid=')]
        assert len(filterid_args) == 1
        ids = filterid_args[0].split('=')[1].split(',')
        assert '33333333' in ids
        assert '22222222' in ids

    def test_msg_types(self, sample_config):
        args = build_rtlamr_args(sample_config)
        msgtype_args = [a for a in args if a.startswith('-msgtype=')]
        assert len(msgtype_args) == 1
        types = msgtype_args[0].split('=')[1].split(',')
        assert 'scm+' in types
        assert 'r900' in types

    def test_custom_parameters_merged(self, sample_config):
        sample_config['custom_parameters']['rtlamr'] = '-unique=false -duration=30m'
        args = build_rtlamr_args(sample_config)
        assert '-unique=false' in args
        assert '-duration=30m' in args

    def test_custom_server_param_removed(self, sample_config):
        sample_config['custom_parameters']['rtlamr'] = '-server=bad:5555 -unique=true'
        args = build_rtlamr_args(sample_config)
        server_args = [a for a in args if a.startswith('-server=')]
        assert len(server_args) == 1
        assert server_args[0] == '-server=127.0.0.1:1234'


class TestBuildRtltcpArgs:
    def test_local_basic(self, sample_config):
        args = build_rtltcp_args(sample_config)
        assert args is not None
        assert '-d 0' in args

    def test_local_custom_device(self, sample_config):
        sample_config['general']['device_id'] = 2
        args = build_rtltcp_args(sample_config)
        assert '-d 2' in args

    def test_remote_returns_none(self, sample_config):
        sample_config['general']['rtltcp_host'] = '192.168.1.100:1234'
        args = build_rtltcp_args(sample_config)
        assert args is None

    def test_custom_parameters(self, sample_config):
        sample_config['custom_parameters']['rtltcp'] = '-s 1024000 -g 40'
        args = build_rtltcp_args(sample_config)
        assert '-s 1024000 -g 40' in args
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_buildcmd.py -v`

Expected: Multiple failures due to current code's `set()` deduplication, `sdl_devices` bug, and bus:address logic.

- [ ] **Step 3: Rewrite buildcmd.py**

Replace `rtlamr2mqtt-addon/app/helpers/buildcmd.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_buildcmd.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/helpers/buildcmd.py rtlamr2mqtt-addon/tests/test_buildcmd.py
git commit -m "refactor: rewrite buildcmd with integer device_id, fix set ordering and sdl_devices bug"
```

---

### Task 6: Rewrite helpers/usb_utils.py

**Files:**
- Modify: `rtlamr2mqtt-addon/app/helpers/usb_utils.py`
- Create: `rtlamr2mqtt-addon/tests/test_usb_utils.py`

- [ ] **Step 1: Write failing tests for usb_utils**

Create `rtlamr2mqtt-addon/tests/test_usb_utils.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from helpers.usb_utils import load_id_file, find_rtl_sdr_devices, get_device_by_index, tickle_rtl_tcp


class TestLoadIdFile:
    def test_loads_valid_ids(self):
        sdl_file = os.path.join(os.path.dirname(__file__), '..', 'app', 'helpers', 'sdl_ids.txt')
        ids = load_id_file(sdl_file)
        assert len(ids) > 0
        assert '0bda:2838' in ids

    def test_ignores_comments(self):
        sdl_file = os.path.join(os.path.dirname(__file__), '..', 'app', 'helpers', 'sdl_ids.txt')
        ids = load_id_file(sdl_file)
        for device_id in ids:
            assert not device_id.startswith('#')


class TestFindRtlSdrDevices:
    @patch('helpers.usb_utils.usb.core.find')
    def test_finds_matching_device(self, mock_find):
        mock_dev = MagicMock()
        mock_dev.idVendor = 0x0bda
        mock_dev.idProduct = 0x2838
        mock_find.return_value = [mock_dev]
        devices = find_rtl_sdr_devices()
        assert len(devices) == 1

    @patch('helpers.usb_utils.usb.core.find')
    def test_no_devices(self, mock_find):
        mock_find.return_value = []
        devices = find_rtl_sdr_devices()
        assert len(devices) == 0

    @patch('helpers.usb_utils.usb.core.find')
    def test_ignores_non_rtlsdr(self, mock_find):
        mock_dev = MagicMock()
        mock_dev.idVendor = 0xFFFF
        mock_dev.idProduct = 0xFFFF
        mock_find.return_value = [mock_dev]
        devices = find_rtl_sdr_devices()
        assert len(devices) == 0


class TestGetDeviceByIndex:
    @patch('helpers.usb_utils.usb.core.find')
    def test_get_first_device(self, mock_find):
        mock_dev = MagicMock()
        mock_dev.idVendor = 0x0bda
        mock_dev.idProduct = 0x2838
        mock_find.return_value = [mock_dev]
        device = get_device_by_index(0)
        assert device is mock_dev

    @patch('helpers.usb_utils.usb.core.find')
    def test_index_out_of_range(self, mock_find):
        mock_dev = MagicMock()
        mock_dev.idVendor = 0x0bda
        mock_dev.idProduct = 0x2838
        mock_find.return_value = [mock_dev]
        device = get_device_by_index(5)
        assert device is None

    @patch('helpers.usb_utils.usb.core.find')
    def test_no_devices(self, mock_find):
        mock_find.return_value = []
        device = get_device_by_index(0)
        assert device is None


class TestTickleRtlTcp:
    @patch('helpers.usb_utils.socket.socket')
    def test_tickle_sends_commands(self, mock_socket_class):
        mock_conn = MagicMock()
        mock_socket_class.return_value = mock_conn
        tickle_rtl_tcp('127.0.0.1:1234')
        mock_conn.connect.assert_called_once()
        assert mock_conn.send.call_count == 2
        mock_conn.close.assert_called_once()

    @patch('helpers.usb_utils.socket.socket')
    def test_tickle_handles_connection_error(self, mock_socket_class):
        mock_conn = MagicMock()
        mock_conn.connect.side_effect = ConnectionRefusedError("refused")
        mock_socket_class.return_value = mock_conn
        # Should not raise
        tickle_rtl_tcp('127.0.0.1:1234')
        mock_conn.close.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_usb_utils.py -v`

Expected: Tests referencing `get_device_by_index` fail (function doesn't exist yet). Others may pass.

- [ ] **Step 3: Rewrite usb_utils.py**

Replace `rtlamr2mqtt-addon/app/helpers/usb_utils.py`:

```python
"""
Helper functions for USB handling
"""

import os
import re
import socket
import logging
from random import randrange
from struct import pack
from time import sleep
import usb.core

logger = logging.getLogger('rtlamr2mqtt')


def load_id_file(sdl_ids_file):
    """
    Load known RTL-SDR device vendor:product IDs from file.
    """
    device_ids = []
    with open(sdl_ids_file, 'r', encoding='utf-8') as f:
        for line in f:
            li = line.strip()
            if re.match(r"^(0[xX])?[A-Fa-f0-9]+:(0[xX])?[A-Fa-f0-9]+$", li):
                device_ids.append(li.lower())
    return device_ids


def find_rtl_sdr_devices():
    """
    Find all connected RTL-SDR devices.
    Returns a list of pyusb device objects.
    """
    sdl_file_path = os.path.join(os.path.dirname(__file__), 'sdl_ids.txt')
    known_ids = load_id_file(sdl_file_path)
    devices_found = []
    for dev in usb.core.find(find_all=True):
        for known_dev in known_ids:
            vid, pid = known_dev.split(':')
            if dev.idVendor == int(vid, 16) and dev.idProduct == int(pid, 16):
                devices_found.append(dev)
                break
    return devices_found


def get_device_by_index(index):
    """
    Get the RTL-SDR device at the given index.
    Returns the pyusb device object, or None if index is out of range.
    """
    devices = find_rtl_sdr_devices()
    if index < len(devices):
        return devices[index]
    return None


def reset_usb_device(device_index):
    """
    Reset the USB device at the given index.
    Returns True if reset was successful, False otherwise.
    """
    device = get_device_by_index(device_index)
    if device is None:
        logger.warning('No RTL-SDR device found at index %d', device_index)
        return False
    try:
        device.reset()
        logger.info('USB device at index %d reset successfully', device_index)
        return True
    except usb.core.USBError as e:
        logger.warning('Failed to reset USB device at index %d: %s', device_index, e)
        return False


def tickle_rtl_tcp(remote_server):
    """
    Connect to rtl_tcp and change some tuner settings. This has proven to
    reset some receivers that are blocked and producing errors.
    """
    SET_FREQUENCY = 0x01
    SET_SAMPLERATE = 0x02

    parts = remote_server.split(':', 1)
    remote_host = parts[0]
    remote_port = int(parts[1]) if len(parts) > 1 else 1234

    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.settimeout(5)
    send_cmd = lambda c, command, parameter: c.send(pack(">BI", int(command), int(parameter)))
    try:
        conn.connect((remote_host, remote_port))
        send_cmd(conn, SET_FREQUENCY, 88e6 + randrange(0, 20) * 1e6)
        sleep(0.2)
        send_cmd(conn, SET_SAMPLERATE, 2048000)
    except socket.error as err:
        logger.debug('Could not tickle rtl_tcp at %s: %s', remote_server, err)
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_usb_utils.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/helpers/usb_utils.py rtlamr2mqtt-addon/tests/test_usb_utils.py
git commit -m "refactor: rewrite usb_utils with index-based device lookup, use pyusb reset"
```

---

### Task 7: Create process_manager.py

This is the core new module — the generic async subprocess wrapper.

**Files:**
- Create: `rtlamr2mqtt-addon/app/process_manager.py`
- Create: `rtlamr2mqtt-addon/tests/test_process_manager.py`

- [ ] **Step 1: Write failing tests for ManagedProcess**

Create `rtlamr2mqtt-addon/tests/test_process_manager.py`:

```python
import asyncio
import os
import pytest
from process_manager import ManagedProcess


@pytest.fixture
def mock_script_dir():
    return os.path.join(os.path.dirname(__file__), '..', 'mock')


class TestManagedProcessStart:
    async def test_start_with_ready_pattern(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
        )
        result = await proc.start()
        assert result is True
        assert proc.is_alive is True
        await proc.stop()

    async def test_start_timeout(self, tmp_path):
        # Script that never prints the ready pattern
        script = tmp_path / 'slow.sh'
        script.write_text('#!/bin/bash\nwhile true; do sleep 1; done\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='slow',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=1.0,
        )
        result = await proc.start()
        assert result is False
        assert proc.is_alive is False

    async def test_start_process_exits_early(self, tmp_path):
        script = tmp_path / 'fail.sh'
        script.write_text('#!/bin/bash\necho "error"\nexit 1\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='fail',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=5.0,
        )
        result = await proc.start()
        assert result is False


class TestManagedProcessStop:
    async def test_stop_terminates(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
        )
        await proc.start()
        await proc.stop()
        assert proc.is_alive is False

    async def test_stop_when_not_started(self):
        proc = ManagedProcess(
            name='test',
            command=['echo', 'hello'],
            ready_pattern='hello',
            ready_timeout=5.0,
        )
        # Should not raise
        await proc.stop()


class TestManagedProcessReadLine:
    async def test_read_lines_from_mock_rtlamr(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtlamr',
            command=[os.path.join(mock_script_dir, 'rtlamr')],
            ready_pattern='GainCount:',
            ready_timeout=10.0,
        )
        await proc.start()
        # Read a few lines — the mock outputs JSON lines after the header
        lines_read = []
        for _ in range(3):
            line = await proc.read_line()
            if line is not None:
                lines_read.append(line)
        assert len(lines_read) > 0
        await proc.stop()

    async def test_read_line_returns_none_after_exit(self, tmp_path):
        script = tmp_path / 'quick.sh'
        script.write_text('#!/bin/bash\necho "READY"\necho "line1"\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='quick',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=5.0,
        )
        await proc.start()
        # Read until we get None (process exited)
        lines = []
        for _ in range(10):
            line = await proc.read_line()
            if line is None:
                break
            lines.append(line)
        assert 'line1' in lines
        assert proc.is_alive is False


class TestManagedProcessRetry:
    async def test_start_with_retry_succeeds(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
            max_retries=3,
            backoff=[0.1, 0.2, 0.3],
        )
        result = await proc.start_with_retry()
        assert result is True
        await proc.stop()

    async def test_start_with_retry_exhausted(self, tmp_path):
        script = tmp_path / 'fail.sh'
        script.write_text('#!/bin/bash\nexit 1\n')
        script.chmod(0o755)
        proc = ManagedProcess(
            name='fail',
            command=[str(script)],
            ready_pattern='READY',
            ready_timeout=1.0,
            max_retries=2,
            backoff=[0.1, 0.1],
        )
        result = await proc.start_with_retry()
        assert result is False


class TestManagedProcessRestart:
    async def test_restart(self, mock_script_dir):
        proc = ManagedProcess(
            name='rtl_tcp',
            command=[os.path.join(mock_script_dir, 'rtl_tcp')],
            ready_pattern='listening...',
            ready_timeout=10.0,
        )
        await proc.start()
        assert proc.is_alive is True
        result = await proc.restart()
        assert result is True
        assert proc.is_alive is True
        await proc.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_process_manager.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'process_manager'`

- [ ] **Step 3: Implement ManagedProcess**

Create `rtlamr2mqtt-addon/app/process_manager.py`:

```python
"""
Generic async subprocess manager with ready detection, retry, and clean shutdown.
"""

import asyncio
import signal
import logging
from shutil import which

logger = logging.getLogger('rtlamr2mqtt')


class ManagedProcess:
    """
    Manages an external process with:
    - Async start with ready-pattern detection
    - Timeout on ready wait
    - Retry with configurable backoff
    - Clean shutdown (SIGTERM -> SIGKILL)
    - Async line reading
    """

    def __init__(
        self,
        name: str,
        command: list[str],
        ready_pattern: str,
        ready_timeout: float = 30.0,
        max_retries: int = 5,
        backoff: list[float] | None = None,
    ):
        self.name = name
        self.command = command
        self.ready_pattern = ready_pattern
        self.ready_timeout = ready_timeout
        self.max_retries = max_retries
        self.backoff = backoff if backoff is not None else [2, 5, 10, 20, 30]
        self._process: asyncio.subprocess.Process | None = None

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> bool:
        """
        Start the process and wait for the ready pattern in stdout.
        Returns True if the process started and is ready, False otherwise.
        """
        if self.is_alive:
            await self.stop()

        # Prepend stdbuf for line-buffered output if available
        full_command = list(self.command)
        stdbuf_path = which('stdbuf')
        if stdbuf_path:
            full_command = [stdbuf_path, '-oL'] + full_command

        logger.info('Starting %s: %s', self.name, ' '.join(full_command))

        try:
            self._process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as e:
            logger.error('Failed to launch %s: %s', self.name, e)
            self._process = None
            return False

        # Wait for ready pattern with timeout
        try:
            ready = await asyncio.wait_for(
                self._wait_for_ready(),
                timeout=self.ready_timeout,
            )
            if ready:
                logger.info('%s is ready', self.name)
            return ready
        except asyncio.TimeoutError:
            logger.error('%s did not become ready within %.1fs', self.name, self.ready_timeout)
            await self.stop()
            return False

    async def _wait_for_ready(self) -> bool:
        """
        Read stdout lines until the ready pattern is found or the process exits.
        """
        while True:
            if self._process.stdout is None:
                return False

            line_bytes = await self._process.stdout.readline()
            if not line_bytes:
                # EOF — process exited
                logger.error('%s exited before becoming ready (exit code: %s)',
                             self.name, self._process.returncode)
                return False

            line = line_bytes.decode('utf-8', errors='replace').strip()
            if line:
                logger.debug('%s: %s', self.name, line)
            if self.ready_pattern in line:
                return True

    async def stop(self):
        """
        Stop the process. Sends SIGTERM, waits 2 seconds, then SIGKILL.
        """
        if self._process is None:
            return

        if self._process.returncode is not None:
            # Already exited
            self._process = None
            return

        logger.info('Stopping %s (pid %d)', self.name, self._process.pid)

        try:
            self._process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning('%s did not exit after SIGTERM, sending SIGKILL', self.name)
                self._process.kill()
                await self._process.wait()
        except ProcessLookupError:
            pass  # Already dead

        logger.info('%s stopped', self.name)
        self._process = None

    async def restart(self) -> bool:
        """
        Stop then start the process.
        """
        await self.stop()
        return await self.start()

    async def start_with_retry(self) -> bool:
        """
        Try to start the process, retrying with backoff on failure.
        Returns True if the process started successfully, False if all retries exhausted.
        """
        if await self.start():
            return True

        for attempt in range(self.max_retries):
            delay = self.backoff[min(attempt, len(self.backoff) - 1)]
            logger.warning(
                '%s failed to start, retry %d/%d in %.1fs',
                self.name, attempt + 1, self.max_retries, delay,
            )
            await asyncio.sleep(delay)
            if await self.start():
                return True

        logger.error('%s failed to start after %d retries', self.name, self.max_retries)
        return False

    async def read_line(self) -> str | None:
        """
        Read one line from the process stdout.
        Returns the stripped line string, or None if the process has exited / stdout closed.
        """
        if self._process is None or self._process.stdout is None:
            return None

        try:
            line_bytes = await self._process.stdout.readline()
        except Exception as e:
            logger.error('Error reading from %s: %s', self.name, e)
            return None

        if not line_bytes:
            # EOF
            return None

        return line_bytes.decode('utf-8', errors='replace').strip()

    async def wait_for_exit(self):
        """
        Wait for the process to exit. Used during intentional shutdown.
        """
        if self._process is not None and self._process.returncode is None:
            await self._process.wait()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_process_manager.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/process_manager.py rtlamr2mqtt-addon/tests/test_process_manager.py
git commit -m "feat: add ManagedProcess async subprocess wrapper with retry and ready detection"
```

---

### Task 8: Create mqtt_publisher.py

**Files:**
- Create: `rtlamr2mqtt-addon/app/mqtt_publisher.py`
- Create: `rtlamr2mqtt-addon/tests/test_mqtt_publisher.py`

- [ ] **Step 1: Write failing tests for MQTTPublisher**

Create `rtlamr2mqtt-addon/tests/test_mqtt_publisher.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mqtt_publisher import MQTTPublisher


@pytest.fixture
def publisher(sample_config):
    queue = asyncio.Queue()
    shutdown = asyncio.Event()
    return MQTTPublisher(
        config=sample_config,
        reading_queue=queue,
        shutdown_event=shutdown,
    )


class TestMQTTPublisherInit:
    def test_creates_instance(self, publisher):
        assert publisher is not None
        assert publisher.base_topic == 'rtlamr'

    def test_builds_tls_context_when_enabled(self, sample_config):
        sample_config['mqtt']['tls_enabled'] = True
        sample_config['mqtt']['tls_ca'] = '/etc/ssl/ca.crt'
        queue = asyncio.Queue()
        shutdown = asyncio.Event()
        pub = MQTTPublisher(config=sample_config, reading_queue=queue, shutdown_event=shutdown)
        assert pub.tls_context is not None

    def test_no_tls_context_when_disabled(self, publisher):
        assert publisher.tls_context is None


class TestMQTTPublisherDiscovery:
    async def test_publish_discovery_all_meters(self, publisher):
        mock_client = AsyncMock()
        await publisher.publish_discovery(mock_client)
        # Should publish one discovery message per meter
        assert mock_client.publish.call_count == len(publisher.meters)

    async def test_discovery_payload_structure(self, publisher):
        mock_client = AsyncMock()
        await publisher.publish_discovery(mock_client)
        call_args = mock_client.publish.call_args_list[0]
        topic = call_args.kwargs.get('topic') or call_args[0][0]
        assert 'homeassistant/device/' in topic
        assert '/config' in topic


class TestMQTTPublisherReadings:
    async def test_publish_reading(self, publisher):
        mock_client = AsyncMock()
        reading = {
            'meter_id': '33333333',
            'consumption': 1978226,
            'message': {'Type': 7, 'TamperPhy': 3},
        }
        await publisher.publish_reading(mock_client, reading)
        # Should publish status, state, and attributes = 3 calls
        assert mock_client.publish.call_count == 3

    async def test_publish_reading_formats_number(self, publisher):
        mock_client = AsyncMock()
        reading = {
            'meter_id': '33333333',
            'consumption': 1978226,
            'message': {'Type': 7},
        }
        await publisher.publish_reading(mock_client, reading)
        # Find the state publish call
        for call in mock_client.publish.call_args_list:
            topic = call.kwargs.get('topic') or call[0][0]
            if '/state' in topic and 'status' not in topic:
                import json
                payload = json.loads(call.kwargs.get('payload') or call[0][1])
                assert payload['reading'] == '001978.226'
                break


class TestMQTTPublisherStatus:
    async def test_publish_online(self, publisher):
        mock_client = AsyncMock()
        await publisher.publish_status(mock_client, 'online')
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        topic = call_args.kwargs.get('topic') or call_args[0][0]
        assert topic == 'rtlamr/status'
        payload = call_args.kwargs.get('payload') or call_args[0][1]
        assert payload == 'online'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_mqtt_publisher.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'mqtt_publisher'`

- [ ] **Step 3: Implement MQTTPublisher**

Create `rtlamr2mqtt-addon/app/mqtt_publisher.py`:

```python
"""
Async MQTT publisher using aiomqtt.
Handles connection, discovery, reading publication, and HA status monitoring.
"""

import asyncio
import ssl
import logging
from json import dumps
from datetime import datetime

import aiomqtt

import helpers.ha_messages as ha_msgs
import helpers.read_output as ro

logger = logging.getLogger('rtlamr2mqtt')


class MQTTPublisher:
    """
    Async MQTT publisher that:
    - Connects to the broker with LWT
    - Publishes HA discovery for all meters
    - Consumes readings from a queue and publishes state/attributes
    - Listens for HA status and re-publishes discovery on HA restart
    - Reconnects with backoff on disconnect
    """

    def __init__(self, config: dict, reading_queue: asyncio.Queue, shutdown_event: asyncio.Event):
        mqtt_config = config['mqtt']
        self.host = mqtt_config['host']
        self.port = mqtt_config['port']
        self.username = mqtt_config['user']
        self.password = mqtt_config['password']
        self.base_topic = mqtt_config['base_topic']
        self.ha_status_topic = mqtt_config['ha_status_topic']
        self.ha_autodiscovery_topic = mqtt_config['ha_autodiscovery_topic']
        self.meters = config['meters']
        self.reading_queue = reading_queue
        self.shutdown_event = shutdown_event

        # Build TLS context if enabled
        self.tls_context = None
        if mqtt_config['tls_enabled']:
            self.tls_context = ssl.create_default_context()
            if mqtt_config['tls_ca']:
                self.tls_context.load_verify_locations(mqtt_config['tls_ca'])
            if mqtt_config['tls_cert'] and mqtt_config['tls_keyfile']:
                self.tls_context.load_cert_chain(mqtt_config['tls_cert'], mqtt_config['tls_keyfile'])
            if mqtt_config['tls_insecure']:
                self.tls_context.check_hostname = False
                self.tls_context.verify_mode = ssl.CERT_NONE

    async def run(self):
        """
        Main loop: connect, publish discovery, consume queue.
        Reconnects with backoff on disconnect.
        """
        while not self.shutdown_event.is_set():
            try:
                will = aiomqtt.Will(
                    topic=f'{self.base_topic}/status',
                    payload='offline',
                    qos=1,
                    retain=False,
                )
                async with aiomqtt.Client(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    tls_context=self.tls_context,
                    will=will,
                ) as client:
                    logger.info('Connected to MQTT broker at %s:%d', self.host, self.port)
                    await self._run_connected(client)
            except aiomqtt.MqttError as e:
                if self.shutdown_event.is_set():
                    break
                logger.warning('MQTT connection lost: %s. Reconnecting in 5s...', e)
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

        logger.info('MQTT publisher shutting down')

    async def _run_connected(self, client: aiomqtt.Client):
        """
        Runs while connected: publish discovery, subscribe to HA status,
        and consume readings concurrently.
        """
        await self.publish_discovery(client)
        await self.publish_status(client, 'online')
        await client.subscribe(self.ha_status_topic, qos=1)

        # Run HA status listener and reading consumer concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._listen_ha_status(client))
            tg.create_task(self._consume_readings(client))

    async def _listen_ha_status(self, client: aiomqtt.Client):
        """
        Listen for HA status messages. Re-publish discovery when HA restarts.
        """
        async for message in client.messages:
            if self.shutdown_event.is_set():
                break
            if message.topic.matches(self.ha_status_topic):
                payload = message.payload.decode('utf-8', errors='replace')
                logger.info('HA status: %s', payload)
                if payload == 'online':
                    await self.publish_discovery(client)
                    await self.publish_status(client, 'online')

    async def _consume_readings(self, client: aiomqtt.Client):
        """
        Consume readings from the queue and publish them.
        """
        while not self.shutdown_event.is_set():
            try:
                reading = await asyncio.wait_for(self.reading_queue.get(), timeout=1.0)
                await self.publish_reading(client, reading)
                self.reading_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def publish_discovery(self, client):
        """
        Publish HA MQTT discovery messages for all configured meters.
        """
        for meter_id, meter_config in self.meters.items():
            discovery_payload = ha_msgs.meter_discover_payload(self.base_topic, meter_config)
            topic = f'{self.ha_autodiscovery_topic}/device/{meter_id}/config'
            await client.publish(
                topic=topic,
                payload=dumps(discovery_payload),
                qos=1,
                retain=False,
            )
            logger.debug('Published discovery for meter %s', meter_id)

    async def publish_reading(self, client, reading: dict):
        """
        Publish a meter reading: status, state, and attributes.
        """
        meter_id = reading['meter_id']
        meter_config = self.meters.get(meter_id, {})
        consumption = reading['consumption']

        # Format the reading if format is configured
        fmt = meter_config.get('format')
        if fmt:
            formatted = ro.format_number(consumption, fmt)
        else:
            formatted = consumption

        # Publish online status
        await self.publish_status(client, 'online')

        # Publish state
        timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
        payload = {'reading': formatted, 'lastseen': timestamp}
        await client.publish(
            topic=f'{self.base_topic}/{meter_id}/state',
            payload=dumps(payload),
            qos=1,
            retain=False,
        )

        # Publish attributes
        attributes = dict(reading['message'])
        attributes['protocol'] = meter_config.get('protocol', 'unknown')
        await client.publish(
            topic=f'{self.base_topic}/{meter_id}/attributes',
            payload=dumps(attributes),
            qos=1,
            retain=False,
        )

        logger.info('Published reading for meter %s: %s', meter_id, formatted)

    async def publish_status(self, client, status: str):
        """
        Publish online/offline status.
        """
        await client.publish(
            topic=f'{self.base_topic}/status',
            payload=status,
            qos=1,
            retain=False,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_mqtt_publisher.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/mqtt_publisher.py rtlamr2mqtt-addon/tests/test_mqtt_publisher.py
git commit -m "feat: add async MQTTPublisher with aiomqtt, discovery, and reconnection"
```

---

### Task 9: Create meter_reader.py

**Files:**
- Create: `rtlamr2mqtt-addon/app/meter_reader.py`
- Create: `rtlamr2mqtt-addon/tests/test_meter_reader.py`

- [ ] **Step 1: Write failing tests for meter_reader**

Create `rtlamr2mqtt-addon/tests/test_meter_reader.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from meter_reader import MeterReader


@pytest.fixture
def mock_rtlamr():
    proc = AsyncMock()
    proc.is_alive = True
    proc.start_with_retry = AsyncMock(return_value=True)
    proc.stop = AsyncMock()
    return proc


@pytest.fixture
def mock_rtltcp():
    proc = AsyncMock()
    proc.is_alive = True
    proc.start_with_retry = AsyncMock(return_value=True)
    proc.stop = AsyncMock()
    return proc


@pytest.fixture
def reader(sample_config, mock_rtlamr, mock_rtltcp):
    queue = asyncio.Queue()
    shutdown = asyncio.Event()
    return MeterReader(
        config=sample_config,
        rtlamr=mock_rtlamr,
        rtltcp=mock_rtltcp,
        reading_queue=queue,
        shutdown_event=shutdown,
        is_remote=False,
    )


class TestMeterReaderParsing:
    async def test_valid_reading_enqueued(self, reader, mock_rtlamr, sample_rtlamr_scm_line):
        """A valid SCM reading for a configured meter should be put on the queue."""
        # Return one valid line then trigger shutdown
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_rtlamr_scm_line
            # Trigger shutdown after first reading
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()

        assert reader.reading_queue.qsize() == 1
        reading = await reader.reading_queue.get()
        assert reading['meter_id'] == '33333333'
        assert reading['consumption'] == 1978226

    async def test_non_matching_id_not_enqueued(self, reader, mock_rtlamr):
        """Lines for meters not in config should be ignored."""
        non_matching_line = '{"Time":"2025-05-05T21:25:10Z","Offset":0,"Length":0,"Type":"R900","Message":{"ID":9999999,"Unkn1":163,"NoUse":0,"BackFlow":0,"Consumption":100,"Unkn3":0,"Leak":0,"LeakNow":0}}'
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return non_matching_line
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()
        assert reader.reading_queue.qsize() == 0

    async def test_non_json_line_ignored(self, reader, mock_rtlamr):
        """Non-JSON lines (rtlamr debug output) should be silently ignored."""
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 'set freq 912600155'
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()
        assert reader.reading_queue.qsize() == 0


class TestMeterReaderSleepCycle:
    async def test_sleep_cycle_when_all_meters_read(self, sample_config, mock_rtlamr, mock_rtltcp):
        """When sleep_for > 0 and all meters read, processes should be stopped then restarted."""
        sample_config['general']['sleep_for'] = 1
        queue = asyncio.Queue()
        shutdown = asyncio.Event()
        reader = MeterReader(
            config=sample_config,
            rtlamr=mock_rtlamr,
            rtltcp=mock_rtltcp,
            reading_queue=queue,
            shutdown_event=shutdown,
            is_remote=False,
        )

        scm_33 = '{"Time":"2025-05-05T21:25:11Z","Offset":0,"Length":0,"Type":"SCM","Message":{"ID":33333333,"Type":7,"TamperPhy":3,"TamperEnc":2,"Consumption":1978226,"ChecksumVal":60151}}'
        scm_22 = '{"Time":"2025-05-05T21:25:11Z","Offset":0,"Length":0,"Type":"SCM","Message":{"ID":22222222,"Type":7,"TamperPhy":0,"TamperEnc":1,"Consumption":9480653,"ChecksumVal":8042}}'

        call_count = 0
        cycle_count = 0
        async def fake_read_line():
            nonlocal call_count, cycle_count
            call_count += 1
            if cycle_count == 0:
                if call_count == 1:
                    return scm_33
                if call_count == 2:
                    return scm_22
                # After second cycle, shutdown
            cycle_count += 1
            shutdown.set()
            return None
        mock_rtlamr.read_line = fake_read_line

        await reader.run()

        # Both processes should have been stopped for sleep
        assert mock_rtlamr.stop.call_count >= 1
        assert mock_rtltcp.stop.call_count >= 1
        # Two readings should be on the queue
        assert queue.qsize() == 2


class TestMeterReaderProcessRestart:
    async def test_restart_on_rtlamr_death(self, reader, mock_rtlamr):
        """If rtlamr dies (read_line returns None), it should be restarted."""
        call_count = 0
        async def fake_read_line():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # Simulate process death
            reader.shutdown_event.set()
            return None
        mock_rtlamr.read_line = fake_read_line
        mock_rtlamr.is_alive = False

        await reader.run()

        # Should have attempted to restart rtlamr
        assert mock_rtlamr.start_with_retry.call_count >= 1

    async def test_shutdown_on_failed_restart(self, reader, mock_rtlamr):
        """If rtlamr can't restart, shutdown_event should be set."""
        mock_rtlamr.read_line = AsyncMock(return_value=None)
        mock_rtlamr.is_alive = False
        mock_rtlamr.start_with_retry = AsyncMock(return_value=False)

        await reader.run()

        assert reader.shutdown_event.is_set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_meter_reader.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'meter_reader'`

- [ ] **Step 3: Implement MeterReader**

Create `rtlamr2mqtt-addon/app/meter_reader.py`:

```python
"""
Async meter reader: reads rtlamr output, parses readings, enqueues them.
Handles sleep/wake cycle and process restart on failure.
"""

import asyncio
import logging

import helpers.read_output as ro

logger = logging.getLogger('rtlamr2mqtt')


class MeterReader:
    """
    Reads lines from the rtlamr ManagedProcess, parses meter readings,
    and puts them on the reading queue for the MQTT publisher.
    """

    def __init__(
        self,
        config: dict,
        rtlamr,
        rtltcp,
        reading_queue: asyncio.Queue,
        shutdown_event: asyncio.Event,
        is_remote: bool,
    ):
        self.config = config
        self.rtlamr = rtlamr
        self.rtltcp = rtltcp
        self.reading_queue = reading_queue
        self.shutdown_event = shutdown_event
        self.is_remote = is_remote
        self.meter_ids = list(config['meters'].keys())
        self.sleep_for = config['general']['sleep_for']

    async def run(self):
        """
        Main reading loop. Reads from rtlamr, parses, enqueues.
        Handles sleep/wake cycle and process restarts.
        """
        while not self.shutdown_event.is_set():
            meters_seen = set()

            # Read until shutdown or all meters seen (when sleep_for > 0)
            while not self.shutdown_event.is_set():
                line = await self.rtlamr.read_line()

                if line is None:
                    # Process died or stdout closed
                    if self.shutdown_event.is_set():
                        break
                    if not self.rtlamr.is_alive:
                        logger.warning('rtlamr process died, attempting restart')
                        if not await self.rtlamr.start_with_retry():
                            logger.error('Failed to restart rtlamr, shutting down')
                            self.shutdown_event.set()
                            return
                    continue

                if not line:
                    # Empty line
                    continue

                # Parse the line
                reading = ro.get_message_for_ids(line, self.meter_ids)
                if reading is None:
                    continue

                # Enqueue the reading
                try:
                    self.reading_queue.put_nowait(reading)
                except asyncio.QueueFull:
                    # Drop oldest reading to make room
                    try:
                        self.reading_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self.reading_queue.put_nowait(reading)
                    logger.warning('Reading queue full, dropped oldest reading')

                meters_seen.add(reading['meter_id'])
                logger.debug('Meter %s reading: %s', reading['meter_id'], reading['consumption'])

                # Check if all meters have been read (sleep_for mode)
                if self.sleep_for > 0 and meters_seen == set(self.meter_ids):
                    logger.info('All %d meters read', len(self.meter_ids))
                    break

            # Sleep/wake cycle
            if self.sleep_for > 0 and not self.shutdown_event.is_set():
                await self._sleep_cycle()

            # If sleep_for == 0 and we got here, the inner loop broke due to shutdown
            if self.sleep_for == 0:
                break

    async def _sleep_cycle(self):
        """
        Stop processes, sleep, restart processes.
        """
        logger.info('Stopping processes for sleep cycle')
        await self.rtlamr.stop()
        if not self.is_remote:
            await self.rtltcp.stop()

        logger.info('Sleeping for %d seconds', self.sleep_for)

        # Cancellable sleep
        sleep_task = asyncio.create_task(asyncio.sleep(self.sleep_for))
        shutdown_task = asyncio.create_task(self.shutdown_event.wait())
        done, pending = await asyncio.wait(
            [sleep_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self.shutdown_event.is_set():
            return

        logger.info('Waking up, restarting processes')

        # Restart rtl_tcp first (if local)
        if not self.is_remote:
            if not await self.rtltcp.start_with_retry():
                logger.error('Failed to restart rtl_tcp after sleep, shutting down')
                self.shutdown_event.set()
                return

        # Restart rtlamr
        if not await self.rtlamr.start_with_retry():
            logger.error('Failed to restart rtlamr after sleep, shutting down')
            self.shutdown_event.set()
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/test_meter_reader.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/app/meter_reader.py rtlamr2mqtt-addon/tests/test_meter_reader.py
git commit -m "feat: add async MeterReader with sleep/wake cycle and process restart"
```

---

### Task 10: Rewrite rtlamr2mqtt.py (Main Entry Point)

**Files:**
- Modify: `rtlamr2mqtt-addon/app/rtlamr2mqtt.py`

- [ ] **Step 1: Rewrite rtlamr2mqtt.py**

Replace the entire contents of `rtlamr2mqtt-addon/app/rtlamr2mqtt.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rtlamr2mqtt - A Home Assistant add-on for RTLAMR
https://github.com/allangood/rtlamr2mqtt/blob/main/LICENSE

This add-on uses the code from:
- https://github.com/bemasher/rtlamr
- https://git.osmocom.org/rtl-sdr
"""

import asyncio
import os
import sys
import signal
import logging
from shutil import which

import helpers.config as cnf
import helpers.buildcmd as cmd
import helpers.usb_utils as usbutil
import helpers.info as i
from process_manager import ManagedProcess
from meter_reader import MeterReader
from mqtt_publisher import MQTTPublisher

# Logging verbosity map
VERBOSITY_MAP = {
    'none': logging.CRITICAL + 1,
    'error': logging.ERROR,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG,
}

logger = logging.getLogger('rtlamr2mqtt')


def setup_logging(verbosity: str):
    """Configure logging with the given verbosity level."""
    logging.basicConfig(
        format='[%(asctime)s] %(levelname)s: %(message)s',
        level=VERBOSITY_MAP.get(verbosity, logging.INFO),
    )
    logger.setLevel(VERBOSITY_MAP.get(verbosity, logging.INFO))


def load_and_validate_config():
    """Load config, set up logging, return config dict or exit."""
    if len(sys.argv) == 2:
        config_path = os.path.join(os.path.dirname(__file__), sys.argv[1])
    else:
        config_path = None

    status, msg, config = cnf.load_config(config_path)
    if status != 'success':
        # Use basic logging since we don't have config yet
        logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s')
        logger.critical(msg)
        sys.exit(1)

    setup_logging(config['general']['verbosity'])
    logger.info('Starting rtlamr2mqtt %s', i.version())
    logger.info(msg)
    return config


async def main():
    """Main async entry point."""
    config = load_and_validate_config()

    shutdown_event = asyncio.Event()
    reading_queue = asyncio.Queue(maxsize=100)

    # Signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    # Determine if rtl_tcp is remote
    rtltcp_host = config['general']['rtltcp_host']
    is_remote = rtltcp_host.split(':')[0] not in ['127.0.0.1', 'localhost']

    # USB setup (sync, before async work)
    if not is_remote and 'RTLAMR2MQTT_USE_MOCK' not in os.environ:
        device_index = config['general']['device_id']
        devices = usbutil.find_rtl_sdr_devices()
        if device_index >= len(devices):
            if len(devices) == 0:
                logger.critical('No RTL-SDR devices found')
            else:
                logger.critical('Device index %d out of range (found %d devices)', device_index, len(devices))
            sys.exit(1)
        logger.info('Found %d RTL-SDR device(s), using index %d', len(devices), device_index)

    # Build commands
    rtltcp_cmd = None
    if not is_remote:
        rtltcp_args = cmd.build_rtltcp_args(config)
        rtltcp_bin = which('rtl_tcp')
        if rtltcp_bin and rtltcp_args is not None:
            rtltcp_cmd = [rtltcp_bin] + rtltcp_args

    rtlamr_args = cmd.build_rtlamr_args(config)
    rtlamr_bin = which('rtlamr')
    if not rtlamr_bin:
        logger.critical('rtlamr binary not found in PATH')
        sys.exit(1)
    rtlamr_cmd = [rtlamr_bin] + rtlamr_args

    # Create managed processes
    rtltcp_proc = ManagedProcess(
        name='rtl_tcp',
        command=rtltcp_cmd or ['echo', 'remote'],
        ready_pattern='listening...',
        ready_timeout=30.0,
    )

    rtlamr_proc = ManagedProcess(
        name='rtlamr',
        command=rtlamr_cmd,
        ready_pattern='GainCount:',
        ready_timeout=30.0,
    )

    # Start rtl_tcp if local
    if not is_remote:
        if not await rtltcp_proc.start_with_retry():
            logger.critical('Failed to start rtl_tcp')
            sys.exit(1)

    # Tickle rtl_tcp to wake it up
    usbutil.tickle_rtl_tcp(rtltcp_host)

    # Start rtlamr
    if not await rtlamr_proc.start_with_retry():
        logger.critical('Failed to start rtlamr')
        if not is_remote:
            await rtltcp_proc.stop()
        sys.exit(1)

    # Create reader and publisher
    reader = MeterReader(
        config=config,
        rtlamr=rtlamr_proc,
        rtltcp=rtltcp_proc,
        reading_queue=reading_queue,
        shutdown_event=shutdown_event,
        is_remote=is_remote,
    )

    publisher = MQTTPublisher(
        config=config,
        reading_queue=reading_queue,
        shutdown_event=shutdown_event,
    )

    # Run reader and publisher concurrently
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(reader.run())
            tg.create_task(publisher.run())
    except* Exception as eg:
        for exc in eg.exceptions:
            if not isinstance(exc, asyncio.CancelledError):
                logger.error('Task error: %s', exc)

    # Cleanup
    logger.info('Shutting down...')
    await rtlamr_proc.stop()
    if not is_remote:
        await rtltcp_proc.stop()
    logger.info('Goodbye!')


if __name__ == '__main__':
    asyncio.run(main())
```

- [ ] **Step 2: Run all tests to check nothing is broken**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add rtlamr2mqtt-addon/app/rtlamr2mqtt.py
git commit -m "refactor: rewrite main entry point with asyncio TaskGroup orchestration"
```

---

### Task 11: Update Dockerfile and config.yaml

**Files:**
- Modify: `rtlamr2mqtt-addon/Dockerfile`
- Modify: `rtlamr2mqtt-addon/Dockerfile.mock`
- Modify: `rtlamr2mqtt-addon/config.yaml`

- [ ] **Step 1: Update Dockerfile — remove expect, keep coreutils**

Replace `rtlamr2mqtt-addon/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.24 AS go-builder

WORKDIR /go/src/app

RUN go install github.com/bemasher/rtlamr@latest \
    && apt-get update \
    && apt-get install -y libusb-1.0-0-dev build-essential git cmake \
    && git clone https://git.osmocom.org/rtl-sdr.git \
    && cd rtl-sdr \
    && mkdir build && cd build \
    && cmake .. -DDETACH_KERNEL_DRIVER=ON -DENABLE_ZEROCOPY=ON -Wno-dev \
    && make \
    && make install

FROM python:3.13-slim

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY --from=go-builder /usr/local/lib/librtl* /lib/
COPY --from=go-builder /go/bin/rtlamr* /usr/bin/
COPY --from=go-builder /usr/local/bin/rtl* /usr/bin/
COPY requirements.txt /tmp
COPY ./app/ $VIRTUAL_ENV/app/

RUN apt-get update \
    && apt-get install -o Dpkg::Options::="--force-confnew" -y \
      libusb-1.0-0 \
      coreutils \
    && apt-get --purge autoremove -y \
    && apt-get clean \
    && find /var/lib/apt/lists/ -type f -delete \
    && pip install -r /tmp/requirements.txt \
    && rm -rf /usr/share/doc /tmp/requirements.txt

STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "/opt/venv/app/rtlamr2mqtt.py"]
```

- [ ] **Step 2: Update Dockerfile.mock — remove expect**

Replace `rtlamr2mqtt-addon/Dockerfile.mock`:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV RTLAMR2MQTT_USE_MOCK=1

COPY mock/ /usr/bin/
COPY requirements.txt /tmp

RUN apt-get update && \
    apt-get install -o Dpkg::Options::="--force-confnew" -y \
      libusb-1.0-0 \
      coreutils && \
    python3 -m venv $VIRTUAL_ENV && \
    pip install -r /tmp/requirements.txt && \
    rm -rf /usr/share/doc /tmp/requirements.txt

COPY ./app/ $VIRTUAL_ENV/app/

STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "/opt/venv/app/rtlamr2mqtt.py"]
```

- [ ] **Step 3: Update config.yaml — change device_id schema to int**

In `rtlamr2mqtt-addon/config.yaml`, change the device_id schema line from:

```yaml
    device_id: "match(^[0-9]{3}:[0-9]{3})?"
```

to:

```yaml
    device_id: "int?"
```

- [ ] **Step 4: Update the example config in rtlamr2mqtt.yaml**

In `rtlamr2mqtt-addon/app/rtlamr2mqtt.yaml`, update the device_id comment section. Replace:

```yaml
  # if you have multiple RTL devices, set the device id to use with this instance.
  # Get the ID running the lsusb command. If not specified, the first device will be used.
  # Example:
  # device_id: '001:010'
```

with:

```yaml
  # if you have multiple RTL devices, set the device index (0, 1, 2, ...) to use.
  # Index corresponds to the order devices are found by librtlsdr.
  # Default is 0 (first device).
  # device_id: 0
```

- [ ] **Step 5: Commit**

```bash
git add rtlamr2mqtt-addon/Dockerfile rtlamr2mqtt-addon/Dockerfile.mock rtlamr2mqtt-addon/config.yaml rtlamr2mqtt-addon/app/rtlamr2mqtt.yaml
git commit -m "chore: update Dockerfile (remove expect), config schema (device_id to int)"
```

---

### Task 12: Delete old mqtt_client.py

**Files:**
- Delete: `rtlamr2mqtt-addon/app/helpers/mqtt_client.py`

- [ ] **Step 1: Remove the old MQTT client wrapper**

```bash
git rm rtlamr2mqtt-addon/app/helpers/mqtt_client.py
```

- [ ] **Step 2: Verify no remaining imports of the old module**

Run: `cd /home/user/allangood/rtlamr2mqtt && grep -r "mqtt_client" rtlamr2mqtt-addon/app/`

Expected: No matches (all references should already be removed in previous tasks).

- [ ] **Step 3: Run all tests**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git rm rtlamr2mqtt-addon/app/helpers/mqtt_client.py
git commit -m "chore: remove old paho-mqtt client wrapper, replaced by mqtt_publisher.py"
```

---

### Task 13: Full Integration Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && pytest tests/ -v --tb=long`

Expected: All tests PASS.

- [ ] **Step 2: Verify the mock environment runs**

Run: `cd /home/user/allangood/rtlamr2mqtt/rtlamr2mqtt-addon && RTLAMR2MQTT_USE_MOCK=1 timeout 10 python app/rtlamr2mqtt.py app/rtlamr2mqtt.yaml 2>&1 || true`

Expected: The app starts, logs show it attempting to connect to MQTT (will fail since no broker is running in test), but it should NOT hang. The key validation is that the asyncio loop starts and the process exits cleanly on timeout/MQTT failure — no blocking.

- [ ] **Step 3: Verify no leftover imports of old modules**

Run: `cd /home/user/allangood/rtlamr2mqtt && grep -rn "import helpers.mqtt_client\|from helpers.mqtt_client\|import helpers.buildcmd\|unbuffer" rtlamr2mqtt-addon/app/`

Expected: No matches for `mqtt_client` or `unbuffer`. `buildcmd` imports should only appear in `rtlamr2mqtt.py`.

- [ ] **Step 4: Final commit with all remaining changes**

```bash
git status
# If any unstaged files remain, add them
git add -A rtlamr2mqtt-addon/
git commit -m "test: add integration smoke test verification"
```
