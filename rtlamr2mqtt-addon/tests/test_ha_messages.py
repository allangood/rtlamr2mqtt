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
        assert device['identifiers'] == ['meter_33333333']
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
        assert reading['unit_of_measurement'] == 'm³'
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
