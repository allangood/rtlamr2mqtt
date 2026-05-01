import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
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
    @patch('helpers.usb_utils.asyncio.open_connection', new_callable=AsyncMock)
    async def test_tickle_sends_commands(self, mock_open_connection):
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.wait_closed = AsyncMock()
        mock_open_connection.return_value = (MagicMock(), mock_writer)

        await tickle_rtl_tcp('127.0.0.1:1234')

        mock_open_connection.assert_called_once()
        assert mock_writer.write.call_count == 2
        mock_writer.close.assert_called_once()

    @patch('helpers.usb_utils.asyncio.open_connection', new_callable=AsyncMock)
    async def test_tickle_handles_connection_error(self, mock_open_connection):
        mock_open_connection.side_effect = ConnectionRefusedError("refused")
        # Should not raise — connection failure before writer is assigned
        await tickle_rtl_tcp('127.0.0.1:1234')
