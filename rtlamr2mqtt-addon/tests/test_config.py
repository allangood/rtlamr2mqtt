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
            assert config['custom_parameters']['rtltcp'] == ''
            assert config['custom_parameters']['rtlamr'] == ''
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
