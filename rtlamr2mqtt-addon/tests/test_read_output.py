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
