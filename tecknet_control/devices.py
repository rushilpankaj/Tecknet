"""Connection state and battery of the TK-MS029, read without PowerShell.

- Bluetooth: paired devices whose name starts with "TK-MS029" are found with
  SetupAPI; WinRT says whether one of them is connected, and the battery
  level is a property of the same device.
- 2.4 GHz: the receiver is only shown as connected after the mouse sends
  input (a receiver plugged in with the mouse off sends nothing).
"""

import asyncio
import ctypes
import logging
import re
import uuid
from ctypes import wintypes
from dataclasses import dataclass

from . import winapi
from .device_ids import device_id, transport

log = logging.getLogger(__name__)

MOUSE_NAME_PREFIX = "TK-MS029"
USB_ACTIVITY_TIMEOUT = 10  # seconds without input before USB counts as idle

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)

DIGCF_PRESENT = 0x02
DIGCF_ALLCLASSES = 0x04
INVALID_HANDLE = ctypes.c_void_p(-1).value


class GUID(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 16)]

    @classmethod
    def from_text(cls, text):
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.ULONG)]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", winapi.ULONG_PTR),
    ]


setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
setupapi.SetupDiGetDevicePropertyW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.POINTER(DEVPROPKEY),
    ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.DWORD,
]
setupapi.SetupDiGetDevicePropertyW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.LPWSTR, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

FRIENDLY_NAME = DEVPROPKEY(GUID.from_text("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)
BATTERY_LEVEL = DEVPROPKEY(GUID.from_text("104ea319-6ee2-4701-bd47-8ddbf425bbe5"), 2)

_ADDRESS = re.compile(r"([0-9A-F]{12})(?:_|$)")


@dataclass
class BluetoothMouse:
    name: str
    address: int
    battery: int | None


@dataclass
class DeviceState:
    connection: str  # "Bluetooth", "2.4 GHz USB" or "None"
    name: str
    connected: bool
    battery: int | None


def _property(devices, info, key):
    buffer = ctypes.create_string_buffer(512)
    kind = wintypes.ULONG(0)
    needed = wintypes.DWORD(0)
    ok = setupapi.SetupDiGetDevicePropertyW(
        devices, ctypes.byref(info), ctypes.byref(key), ctypes.byref(kind),
        buffer, len(buffer), ctypes.byref(needed), 0,
    )
    return buffer.raw[:needed.value] if ok else None


def _instance_id(devices, info):
    buffer = ctypes.create_unicode_buffer(512)
    if setupapi.SetupDiGetDeviceInstanceIdW(devices, ctypes.byref(info), buffer, len(buffer), None):
        return buffer.value.upper()
    return ""


def paired_bluetooth_mice(prefix=MOUSE_NAME_PREFIX):
    found = []
    for enumerator in ("BTHLE", "BTHENUM"):
        devices = setupapi.SetupDiGetClassDevsW(None, enumerator, None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
        if not devices or devices == INVALID_HANDLE:
            continue
        try:
            index = 0
            info = SP_DEVINFO_DATA(cbSize=ctypes.sizeof(SP_DEVINFO_DATA))
            while setupapi.SetupDiEnumDeviceInfo(devices, index, ctypes.byref(info)):
                index += 1
                raw_name = _property(devices, info, FRIENDLY_NAME)
                name = raw_name.decode("utf-16-le").rstrip("\0") if raw_name else ""
                if not name.upper().startswith(prefix.upper()):
                    continue
                match = _ADDRESS.search(_instance_id(devices, info).split("\\")[-1])
                if not match:
                    continue
                battery_raw = _property(devices, info, BATTERY_LEVEL)
                battery = battery_raw[0] if battery_raw else None
                found.append(BluetoothMouse(name, int(match.group(1), 16), battery))
        finally:
            setupapi.SetupDiDestroyDeviceInfoList(devices)
    return found


async def _bluetooth_connected(address):
    from winrt.windows.devices.bluetooth import BluetoothConnectionStatus, BluetoothLEDevice

    device = await BluetoothLEDevice.from_bluetooth_address_async(address)
    if device is None:
        return False
    try:
        return device.connection_status == BluetoothConnectionStatus.CONNECTED
    finally:
        try:
            device.close()
        except Exception:
            pass


def bluetooth_connected(address):
    try:
        return asyncio.run(_bluetooth_connected(address))
    except Exception:
        return False


def usb_receiver_present(target_ids):
    for name in winapi.raw_mouse_device_names():
        if transport(name) == "usb" and device_id(name) in target_ids:
            return True
    return False


def read_state(target_ids, seconds_since_usb_input):
    """seconds_since_usb_input: None when the mouse never sent input over USB."""
    try:
        for mouse in paired_bluetooth_mice():
            if bluetooth_connected(mouse.address):
                return DeviceState("Bluetooth", mouse.name, True, mouse.battery)
    except Exception:
        log.exception("Bluetooth check failed")
    recent = seconds_since_usb_input is not None and seconds_since_usb_input <= USB_ACTIVITY_TIMEOUT
    if recent and usb_receiver_present(target_ids):
        return DeviceState("2.4 GHz USB", "TK-MS029", True, None)
    return DeviceState("None", "", False, None)
