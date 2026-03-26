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
