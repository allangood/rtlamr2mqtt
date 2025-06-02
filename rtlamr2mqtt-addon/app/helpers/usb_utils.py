"""
Helper functions for USB handling
"""

from fcntl import ioctl
from stat import S_ISCHR
from random import randrange
from struct import pack
from time import sleep
import os
import re
import usb.core
import socket

def load_id_file(sdl_ids_file):
    """
    Load SDL file id
    """
    device_ids = []
    with open(sdl_ids_file, 'r', encoding='utf-8') as f:
        for line in f:
            li = line.strip()
            if re.match(r"(^(0[xX])?[A-Fa-f0-9]+:(0[xX])?[A-Fa-f0-9]+$)", li) is not None:
                device_ids.append(line.rstrip().lstrip().lower())
    return device_ids

def find_rtl_sdr_devices():
    """
    Find a valid RTL device
    """
    # Load the list of all supported device ids
    sdl_file_path = os.path.join(os.path.dirname(__file__), 'sdl_ids.txt')
    DEVICE_IDS = load_id_file(sdl_file_path)
    devices_found = []
    for dev in usb.core.find(find_all = True):
        for known_dev in DEVICE_IDS:
            usb_id, usb_vendor = known_dev.split(':')
            if dev.idVendor == int(usb_id, 16) and dev.idProduct == int(usb_vendor, 16):
                devices_found.append(f'{dev.bus:03d}:{dev.address:03d}')
                break
    return devices_found

def reset_usb_device(usbdev):
    """
    Reset USB port
    """
    if usbdev is not None and ':' in usbdev:
        busnum, devnum = [int(x) for x in usbdev.split(':')]
        filename = f"/dev/bus/usb/{busnum:03d}/{devnum:03d}"
        if os.path.exists(filename) and S_ISCHR(os.stat(filename).st_mode):
            #define USBDEVFS_RESET_IO('U', 20)
            USBDEVFS_RESET = ord('U') << (4*2) | 20
            fd = open(filename, "wb")
            result = int(ioctl(fd, USBDEVFS_RESET, 0)) == 0
            fd.close()
            return result
    return False

def tickle_rtl_tcp(remote_server):
    """
    Connect to rtl_tcp and change some tuner settings. This has proven to
    reset some receivers that are blocked and producing errors.
    """
    SET_FREQUENCY = 0x01
    SET_SAMPLERATE = 0x02

    # extract host and port from remote_server string
    parts = remote_server.split(':', 1)
    remote_host = parts[0]
    remote_port = int(parts[1]) if parts[1:] else 1234
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.settimeout(5) # 5 seconds
    send_cmd = lambda c, command, parameter: c.send(pack(">BI", int(command), int(parameter)))
    try:
        conn.connect((remote_host, remote_port))
        send_cmd(conn, SET_FREQUENCY, 88e6 + randrange(0, 20)*1e6) # random freq
        sleep(0.2)
        send_cmd(conn, SET_SAMPLERATE, 2048000)
    except socket.error as err:
        pass
    conn.close()