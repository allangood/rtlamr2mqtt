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
