import json
import unittest
from unittest.mock import MagicMock, patch

from core.device import device
from core.device.command import DeviceCommand
import core.api
import tests.api

test_api = tests.api.TestApi()


def configured_devices():
    return {"deviceA", "deviceB"}


class DeviceTests(unittest.TestCase):
    @patch("core.api.configured_devices", configured_devices)
    @patch("core.api._device_command", test_api.device_command)
    def test_skip_device_commands(self):
        device.pump_on("deviceA")
        device.pump_on("deviceB")
        device.pump_on("deviceC")
        self.assertEqual(test_api.devices, {"deviceA": {"device_on": True}, "deviceB": {"device_on": True}})

        # We can ignore the check against configured_devices
        core.api.device_command(DeviceCommand.pump_on("deviceC"), skip_missing=False)
        self.assertEqual(
            test_api.devices,
            {"deviceA": {"device_on": True}, "deviceB": {"device_on": True}, "deviceC": {"device_on": True}},
        )

    @patch("core.api._get", new_callable=MagicMock)
    def test_configured_devices(self, get_config):
        get_config.return_value = json.loads(
            """{
            "devices": {
              "bftc-device-2": {
                "enabled": true
              },
              "plc.ValveGroup.Valve2": {
                "enabled": true
              }
            },
            "mappings": {
              "SM_SIMPLE_HEATER_DEVICE": "bftc-device-2",
              "SM_SIMPLE_HEATER": "bftc-device-2.heaters.1",
              "SM_SIMPLE_TEMPERATURE": "bftc-device-2.channels.5.temperature",
              "V2": "plc.ValveGroup.Valve2",
              "V2_ENABLED": "plc.ValveGroup.Valve2.bValveCMD",
              "V2_ERROR_VALUE": "plc.ValveGroup.Valve2.statusInfo.errorBit",
              "EXTRA_MAPPING": "not-a-device"
            }
        }"""
        )
        self.assertEqual(
            core.api.configured_devices(),
            {
                "V2",
                "V2_ENABLED",
                "V2_ERROR_VALUE",
                "SM_SIMPLE_TEMPERATURE",
                "SM_SIMPLE_HEATER",
                "SM_SIMPLE_HEATER_DEVICE",
                "EXTRA_MAPPING",
            },
        )

        core.api.configured_devices.cache_clear()
        get_config.return_value["devices"]["bftc-device-2"]["enabled"] = False
        get_config.return_value["devices"]["plc.ValveGroup.Valve2"]["enabled"] = False
        self.assertEqual(
            core.api.configured_devices(),
            {
                "EXTRA_MAPPING",
            },
        )

        core.api.configured_devices.cache_clear()
        get_config.return_value["devices"]["bftc-device-2"]["enabled"] = False
        get_config.return_value["devices"]["plc.ValveGroup.Valve2"]["enabled"] = True
        self.assertEqual(
            core.api.configured_devices(),
            {
                "V2",
                "V2_ENABLED",
                "V2_ERROR_VALUE",
                "EXTRA_MAPPING",
            },
        )

        core.api.configured_devices.cache_clear()
        get_config.return_value["devices"]["bftc-device-2"]["enabled"] = True
        get_config.return_value["devices"]["plc.ValveGroup.Valve2"]["enabled"] = False
        self.assertEqual(
            core.api.configured_devices(),
            {
                "SM_SIMPLE_TEMPERATURE",
                "SM_SIMPLE_HEATER",
                "SM_SIMPLE_HEATER_DEVICE",
                "EXTRA_MAPPING",
            },
        )
