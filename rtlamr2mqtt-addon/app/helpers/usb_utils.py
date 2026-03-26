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