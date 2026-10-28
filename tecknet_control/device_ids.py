"""Short, stable identifiers for mice, taken from their Windows device paths.

USB:       \\\\?\\HID#VID_25A7&PID_FA61&MI_01&COL01#...   -> "25A7:FA61"
Bluetooth: \\\\?\\HID#{00001812-...}_DEV_VID&0225A7_PID&FAA0_... -> "25A7:FAA0"
Other:     \\\\?\\HID#ELAN0527&COL01#...                  -> "ELAN0527"
"""

import re

# TECKNET TK-MS029: 2.4 GHz receiver and Bluetooth LE.
TECKNET_IDS = ("25A7:FA61", "25A7:FAA0")

_VID_PID = re.compile(r"VID[_&](?:00|02)?([0-9A-F]{4})[_&]PID[_&]([0-9A-F]{4})")
_HID_NAME = re.compile(r"HID#([^#&]+)")


def device_id(device_path):
    path = (device_path or "").upper()
    match = _VID_PID.search(path)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    match = _HID_NAME.search(path)
    return match.group(1) if match else ""


def transport(device_path):
    """"usb" for the 2.4 GHz receiver (and other USB mice), "bluetooth" otherwise."""
    path = (device_path or "").upper()
    if "{00001812-" in path or "BTHLE" in path or "BTHENUM" in path:
        return "bluetooth"
    return "usb" if "VID_" in path else "other"
