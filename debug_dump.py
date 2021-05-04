import json
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path

import win32com.client
import wmi

c = wmi.WMI()


class PnpDeviceProperties(Enum):
    ACPI_PATH = "DEVPKEY_Device_BiosDeviceName"
    DRIVER_KEY = "DEVPKEY_Device_Driver"
    LOCATION_PATHS = "DEVPKEY_Device_LocationPaths"
    FRIENDLY_NAME = "DEVPKEY_Device_FriendlyName"
    BUS_DEVICE_FUNCTION = "DEVPKEY_Device_LocationInfo"
    BUS_REPORTED_NAME = "DEVPKEY_Device_BusReportedDeviceDesc"
    BUS_RELATIONS = "DEVPKEY_Device_BusRelations"


def get_property_from_wmi(instance_id, prop: PnpDeviceProperties):
    try:
        return c.query(f"SELECT * FROM Win32_PnPEntity WHERE PNPDeviceID = '{instance_id}'")[0].GetDeviceProperties([prop.value])[0][0].Data
    except Exception:
        return None


def build_dict(instance):
    pnp = c.query(f"SELECT * FROM Win32_PnPEntity WHERE PNPDeviceID = '{instance}'")[0].GetDeviceProperties()[0]
    d = {}
    for i in pnp:
        if isinstance(i.Data, win32com.client.CDispatch):
            # Probably useless
            d[i.KeyName] = "Removed for garbage"
        else:
            d[i.KeyName] = i.Data
    return d


controllers = []

all_devices = {}
start = time.time()


def recurse_bus(instance_id):
    device = build_dict(instance_id)
    all_devices[instance_id] = device

    device["devices"] = {}
    for f in device.get(PnpDeviceProperties.BUS_RELATIONS.value, []):
        if f.startswith("USB"):
            device["devices"][f] = recurse_bus(f)

    return device


for e in c.Win32_USBController():
    controller = build_dict(e.PNPDeviceID)
    all_devices[e.PNPDeviceID] = dict(controller)

    if controller.get(PnpDeviceProperties.BUS_RELATIONS.value, None):
        controller["root_hub"] = recurse_bus(controller[PnpDeviceProperties.BUS_RELATIONS.value][0])

    controllers.append(controller)
end = time.time()
controllers.append({"duration": end - start})


usbdump_path = Path("resources/usbdump.exe")

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    usbdump_path = Path(sys._MEIPASS) / usbdump_path

usbdump = json.loads(subprocess.run(usbdump_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode())

print(json.dumps({"wmitest": controllers, "usbdump": usbdump}, sort_keys=True))
