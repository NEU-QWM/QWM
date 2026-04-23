import unittest
from unittest.mock import MagicMock, patch

import core.api
import automation
import tests.api
from core.state_machine.exceptions import OperationNotFound, StateMachineNotRunning
from core.state_machine.state_machine import OperationParametersNotFound

patch.TEST_PREFIX = (
    "test",
    "setUp",
)

test_api = tests.api.TestApi()


@patch("core.api", new=test_api)
@patch("sm.simple.statemachine.state", test_api.state)
class HandlerTest(unittest.TestCase):
    def setUp(self):
        self.state = core.api.state
        self.state.clear()
        core.api.state.update({"heaterPowerOnTemp": 10, "heaterPowerOffTemp": 20})

    def tearDown(self):
        automation.stop_automation(True)

    def test_list_automations(self):
        statemachine_names = automation.list_automations()
        self.assertEqual(
            statemachine_names,
            ["manual", "simple", "milestone-a", "sentinel-test", "dilution-systems", "helium-systems", "automation-test", "fse"],
        )

    def test_start_raises(self):
        with self.assertRaises(AttributeError):
            automation.start_automation("nonexistent")

    @patch("tests.api.TestApi.configured_devices", MagicMock())
    def test_start_raises_devices(self):
        # Passes the error properly up to the caller
        core.api.configured_devices.side_effect = Exception("Failed to fetch configured devices...")
        with self.assertRaisesRegex(Exception, "Failed to fetch") as cm:
            automation.start_automation("simple")

    def test_stop(self):
        automation.start_automation("simple")
        self.assertTrue(automation.handler._statemachine)
        self.assertTrue(automation.sentinel_handler.sentinel)
        automation.stop_automation()
        self.assertEqual(automation.handler._statemachine, None)
        self.assertEqual(automation.sentinel_handler.sentinel, None)

    def test_stop_does_not_raise_parameter(self):
        automation.stop_automation(skip_if_not_running=True)

    def test_check_with_sentinel_and_sentry(self):
        automation.start_automation("simple")
        alerts = automation.check_with_sentinel_and_sentry({"SM_SIMPLE_TEMPERATURE": 0})
        self.assertEqual(alerts, [])
        alerts = automation.check_with_sentinel_and_sentry({"SM_SIMPLE_TEMPERATURE": 910})
        self.assertGreaterEqual(len(alerts), 1)

    def test_check_with_sentinel_only(self):
        automation.start_automation("simple")
        alerts = automation.check_with_sentinel({"SM_SIMPLE_TEMPERATURE": 910}, {"SM_SIMPLE_TEMPERATURE": 910})
        self.assertEqual(alerts, [])
        alerts = automation.check_with_sentinel({"SM_SIMPLE_TEMPERATURE": 0}, {"SM_SIMPLE_TEMPERATURE": 910})
        self.assertGreaterEqual(len(alerts), 1)

    def test_start_operation_raises_parameters_not_found(self):
        automation.start_automation("simple")
        self.state.clear()
        with self.assertRaises(OperationParametersNotFound):
            automation.start_operation("StartSystem", {})
        automation.stop_automation()

    def test_start_operation_succeeds(self):
        self.state["SM_SIMPLE_TEMPERATURE"] = 0
        automation.start_automation("simple")
        op = automation.start_operation("StartSystem", {"heaterPowerOnTemp": 10, "heaterPowerOffTemp": 20})
        self.assertIn("uuid", op)
        automation.stop_automation()

    def test_start_operation_default_parameters_are_used(self):
        self.state["SM_SIMPLE_TEMPERATURE"] = 0
        automation.start_automation("simple")
        automation.start_operation("StartSystem", {})
        self.assertDictEqual(
            automation.handler.statemachine.current_operation.parameters,
            {"heaterPowerOnTemp": 10, "heaterPowerOffTemp": 20},
        )
        automation.stop_automation()

    def test_start_operation_user_parameters_are_used(self):
        self.state["SM_SIMPLE_TEMPERATURE"] = 0
        automation.start_automation("simple")
        automation.start_operation("StartSystem", {"heaterPowerOnTemp": 1, "heaterPowerOffTemp": 3})
        self.assertDictEqual(
            automation.handler.statemachine.current_operation.parameters,
            {"heaterPowerOnTemp": 1, "heaterPowerOffTemp": 3},
        )
        automation.stop_automation()

    def test_get_operations(self):
        # Starts into Manual mode
        automation.start_automation("simple")
        ops = automation.get_operations()
        self.assertEqual(len(ops), 1)
        self.assertNotIn("valid", ops[0])
        self.assertNotIn("validations", ops[0])

        ops = automation.get_operations(include_validations=True)
        self.assertEqual(len(ops), 1)
        self.assertIn("valid", ops[0])
        self.assertIn("validations", ops[0])
        self.assertIn("procedure_errors", ops[0]["validations"])
        self.assertIn("operation_errors", ops[0]["validations"])
        automation.stop_automation()

    def test_get_operation_by_name_or_id(self):
        # Starts into Manual mode
        automation.start_automation("simple")
        ops = automation.get_operations()
        self.assertEqual(automation.get_operation(ops[0]["name"]), automation.get_operation(ops[0]["operationId"]))
        automation.stop_automation()

    def test_get_operation_parameters(self):
        # Starts into Manual mode
        automation.start_automation("simple")
        params = automation.get_operation_parameters("StartSystem")
        self.assertDictEqual({"heaterPowerOnTemp": 10, "heaterPowerOffTemp": 20}, params)
        automation.stop_automation()

    def test_get_running_operation(self):
        # Starts into Manual mode
        automation.start_automation("simple")
        op = automation.get_running_operation()
        self.assertEqual(op["name"], "Manual")
        automation.stop_automation()

    def test_get_procedure_graph(self):
        # Starts into Manual mode
        automation.start_automation("simple")
        procedures = automation.get_procedure_graph()
        self.assertIn("nodes", procedures)
        self.assertIn("edges", procedures)
        self.assertIn("name", procedures["nodes"][0])
        automation.stop_automation()

    def test_handler_functions_raise_state_machine_not_running(self):
        """
        These functions should raise StateMachineNotRunning
        """
        funcs = [
            (automation.stop_automation, ()),
            (automation.start_operation, ("undefined", {})),
            (automation.get_operations, ()),
            (automation.get_operation, ("undefined",)),
            (automation.get_operation_parameters, ("undefined",)),
            (automation.get_running_operation, ()),
            (automation.get_procedure_graph, ()),
        ]
        for fn, args in funcs:
            with self.assertRaises(
                StateMachineNotRunning, msg=f"Calling {fn.__qualname__} did not raise StateMachineNotRunning"
            ):
                fn(*args)

    @patch("sm.simple.statemachine.state", tests.api.TestApi().state)
    def test_handler_functions_raise_operation_not_found(self):
        """
        These functions should raise OperationNotFound
        """
        automation.start_automation("simple")
        funcs = [
            (automation.start_operation, ("undefined", {})),
            # XXX (automation.get_operation, ("undefined",)),
            (automation.get_operation_parameters, ("undefined",)),
        ]

        for fn, args in funcs:
            with self.assertRaises(OperationNotFound, msg=f"Calling {fn.__qualname__} did not raise OperationNotFound"):
                fn(*args)
        automation.stop_automation()
