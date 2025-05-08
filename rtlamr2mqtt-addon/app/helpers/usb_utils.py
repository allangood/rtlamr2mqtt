import os
import re
import usb.core
from fcntl import ioctl
from stat import S_ISCHR

def load_id_file(sdl_ids_file):
    device_ids = []
    with open(sdl_ids_file) as f:
        for line in f:
            li = line.strip()
            if re.match(r"(^(0[xX])?[A-Fa-f0-9]+:(0[xX])?[A-Fa-f0-9]+$)", li) is not None:
                device_ids.append(line.rstrip().lstrip().lower())
    return device_ids

def find_rtl_sdr_devices():
    # Load the list of all supported device ids
    sdl_file_path = os.path.join(os.path.dirname(__file__), 'sdl_ids.txt')
    DEVICE_IDS = load_id_file(sdl_file_path)
    devices_found = []
    for dev in usb.core.find(find_all = True):
        for known_dev in DEVICE_IDS:
            usb_id, usb_vendor = known_dev.split(':')
            if dev.idVendor == int(usb_id, 16) and dev.idProduct == int(usb_vendor, 16):
                devices_found.append('{:03d}:{:03d}'.format(dev.bus, dev.address))
                break
    return devices_found

def reset_usb_device(usbdev):
    if usbdev is not None and ':' in usbdev:
        busnum, devnum = usbdev.split(':')
        filename = "/dev/bus/usb/{:03d}/{:03d}".format(int(busnum), int(devnum))
        if os.path.exists(filename) and S_ISCHR(os.stat(filename).st_mode):
            #define USBDEVFS_RESET_IO('U', 20)
            USBDEVFS_RESET = ord('U') << (4*2) | 20
            fd = open(filename, "wb")
            result = int(ioctl(fd, USBDEVFS_RESET, 0)) == 0
            fd.close()
            return result
    return False