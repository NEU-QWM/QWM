import unittest
from unittest.mock import MagicMock, call
from unittest.mock import patch

from core.device.command import DeviceCommand
from core.device.command_queue import CommandQueue
from core.state_machine.exceptions import ProcedureError
from sm.general.helpers import Helpers

import core.api
import tests.api

patch.TEST_PREFIX = (
    "test",
    "setUp",
)


@patch("core.api", new=tests.api.TestApi())
class TestCommandQueue(unittest.TestCase):
    def setUp(self):
        core.api.state.update(
            {
                "V001": True,
                "V002": True,
                "V001_ENABLED": True,
                "V002_ENABLED": True,
                "B1A": True,
                "B1B": True,
                "B1A_ENABLED": True,
                "B1B_ENABLED": False,
            }
        )
        self.queue = CommandQueue()
        core.api.device_command = MagicMock()

    def test_queue_empty(self):
        self.assertTrue(self.queue.empty)
        self.queue.queue_valves_off(["V001"])
        self.assertFalse(self.queue.empty)
        self.queue.execute_queued_commands()
        self.assertTrue(self.queue.empty)

    def test_queue_execution(self):
        self.queue.queue_valves_off(["V001", "V002"])
        self.queue.queue_pumps_on(["B1A", "B1B"])  # B1A is already enabled
        self.queue.execute_queued_commands()
        self.assertTrue(self.queue.empty)
        self.assertEqual(core.api.device_command.call_count, 3)
        expected = [
            DeviceCommand(device_id="V001", payload={"valveOnOff": False}),
            DeviceCommand(device_id="V002", payload={"valveOnOff": False}),
            DeviceCommand(device_id="B1B", payload={"pumpStartStop": True}),
        ]
        expected_calls = [call(device_command) for device_command in expected]
        core.api.device_command.assert_has_calls(expected_calls)

    def test_set_state_disable_all(self):
        self.queue.set_state({})
        self.assertEqual(set(Helpers.all_pumps), set([c.device_id for c in self.queue.pump_commands if not c.enable]))
        self.assertEqual(set(Helpers.all_valves), set([c.device_id for c in self.queue.valve_commands if not c.enable]))

    def test_set_state(self):
        self.queue.set_state({"valves": ["V001"], "pumps": ["B1A"]})
        self.assertEqual(
            set(Helpers.all_pumps) - {"B1A"}, set([c.device_id for c in self.queue.pump_commands if not c.enable])
        )
        self.assertEqual(
            set(Helpers.all_valves) - {"V001"}, set([c.device_id for c in self.queue.valve_commands if not c.enable])
        )
        self.assertEqual({"B1A"}, set([c.device_id for c in self.queue.pump_commands if c.enable]))
        self.assertEqual({"V001"}, set([c.device_id for c in self.queue.valve_commands if c.enable]))

    def test_set_state_keeps_ordering(self):
        self.queue.set_state({"valves": ["V002", "V001"]})
        self.assertEqual(["V002", "V001"], [c.device_id for c in self.queue.valve_commands if c.enable])


@patch("core.api", new=tests.api.TestApi())
class TestCommandQueueMissingDeviceOrMappings(unittest.TestCase):
    def setUp(self):
        core.api.state.clear()

    def test_missing_device(self):
        core.api.state.update(
            {
                "V001": True,
                "V001_ENABLED": True,
            }
        )
        queue = CommandQueue()
        queue.queue_valves_off(["V001", "nonexistant"])
        # Should not raise a HTTP error
        queue.execute_queued_commands()

    def test_silent_fail_in_get_list(self):
        """
        The endpoint behind get_list silently drops mappings that exist, but
        don't return proper values, i.e. the right hand side of the mapping
        points to incorrect value.
        """
        core.api.state.update(
            {
                "V001": True,
                "V001_ENABLED": True,
            }
        )
        queue = CommandQueue()
        queue.queue_valves_off(["V001", "nonexistant"])
        core.api.get_list = MagicMock()
        core.api.get_list.return_value = {}
        with self.assertRaisesRegex(ProcedureError, "Failed getting value for V001_ENABLED"):
            queue.execute_queued_commands()
