import time
import unittest
from unittest.mock import MagicMock, patch

import core.api
import tests.api

from core.device.command import AlertCommand, AlertSeverity
from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import Initial, Manual, OperationProcedure, Procedure
from core.state_machine.exceptions import ValidationError
from core.state_machine.state_machine import StateMachine

patch.TEST_PREFIX = ("test", "setUp",)


# Two different Procedures use this. Thus defined as separate function
def on_validate(parameters):
    value = parameters["STEP_SIZE"]
    if value >= 7:
        pass
    else:
        yield ValidationError(-1, "Invalid STEP_SIZE")


class Step(OperationProcedure):
    name = "Step"
    operation_name = "Step"
    required_parameters = ["STEP_SIZE"]

    def validate(self, parameters, state):
        yield from on_validate(parameters)


class OtherStep(OperationProcedure):
    name = "OtherStep"
    operation_name = "OtherStep"
    required_parameters = ["STEP_SIZE"]

    def validate(self, parameters, state):
        yield from on_validate(parameters)


class Final(OperationProcedure):
    name = "Final"
    operation_name = "Final"
    required_parameters = ["STEP_SIZE"]

    def validate(self, parameters, state):
        value = parameters["STEP_SIZE"]
        if value >= 5:
            pass
        else:
            yield ValidationError(-1, "Invalid STEP_SIZE")

    def idle(self, parameters):
        pass


class Tertiary(OperationProcedure):
    name = "Tertiary"
    operation_name = "Tertiary"
    required_parameters = ["OPTION"]

    def validate(self, parameters, state):
        yield ValidationError(-1, "This always fails")

    def validate_operation(self, from_procedure, operation, parameters, state):
        if parameters["OPTION"] != "b":
            pass
        else:
            yield ValidationError(-1, "Operation validation failed")


machine_with_validators = StateMachineConfig(
    name="machine_with_validators",
    transitions=(
        (Initial, Step),
        (Initial, OtherStep),
        (Initial, Initial),
        (Step, Final),
        (Step, Tertiary),
    ),
    parameter_mapping={"OPTION": "option", "STEP_SIZE": "step_size"},
)


@patch("core.api", new=tests.api.TestApi())
class StateMachineValidationTests(unittest.TestCase):
    def setUp(self):
        self.state = core.api.state
        self.state.clear()
        self.state.update({"option": "a", "step_size": 6})
        self.machine = StateMachine(machine_with_validators, start=False)
        core.api.alert = MagicMock()

    def tearDown(self):
        pass

    def find_operation(self, operations, start, procs, goal):
        operation = [
            op
            for op in operations
            if op.start.name == start and [p.name for p in op.procedures] == procs and op.static_name == goal
        ]
        self.assertTrue(operation)
        return operation[0]

    def test_validation_works(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        ops = self.machine.get_operations(validate=False)
        self.assertEqual(len(ops), 5, f"Expected to have 5 initial operations, got {len(ops)}")

        ops = self.machine.get_operations(validate=True)
        self.assertEqual(len(ops), 1, f"Expected to have 1 initial operations, got {len(ops)}")

    def test_operation_validation_passes(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        operations = list(self.machine.get_operations(validate=False))
        operation = self.find_operation(operations, "Initial", ["Step"], "Step")

        self.machine.run_operation(operation, {"STEP_SIZE": 7})

        ops = self.machine.get_operations(validate=True)
        self.assertEqual(len(ops), 2, "Expected to see 2 user operation in the step state")
        self.assertEqual(sorted([operation.static_name for operation in ops]), ["Final", "Manual"])

    def test_operation_validation_fails(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        operations = list(self.machine.get_operations(validate=False))
        operation = self.find_operation(operations, "Initial", ["Step"], "Step")
        self.machine.run_operation(operation, {"STEP_SIZE": 6})

        self.assertEqual(core.api.alert.call_count, 1)
        self.assertTrue(isinstance(core.api.alert.call_args[0][0], AlertCommand))
        self.assertEqual(core.api.alert.call_args[0][0].text, 'Validation of procedure "Step" failed: Invalid STEP_SIZE')

        self.assertEqual(self.machine.current_procedure, Manual)

    def test_operation_validation_fails_thread_exits(self):
        import threading
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        operations = list(self.machine.get_operations(validate=False))
        operation = self.find_operation(operations, "Initial", ["Step"], "Step")
        self.machine.run_operation(operation, {"STEP_SIZE": 6}, threaded=True)
        time.sleep(0.1)
        self.assertEqual(self.machine.current_procedure, Manual)
        self.assertEqual(threading.active_count(), 1)


# TODO: This feature was not used in actual code, see if it needs to be included
#    def test_command_parameter_validation(self):
#        time.sleep(0.1)
#        self.assertEqual(
#            self.machine.current_procedure, self.machine.procedures.Initial, "Expected to be in the initial state!"
#        )
#        with self.assertRaises(OperationFailedToStart):
#            self.process.start_operation("Step", {"STEP_SIZE": 11})
#
#    def test_list_option_validation(self):
#        self.assertEqual(
#            self.machine.current_procedure, self.machine.procedures.Initial, "Expected to be in the initial state!"
#        )
#        with self.assertRaises(OperationFailedToStart):
#            self.process.start_operation("Tertiary", {"OPTION": "e"})
#
#    def test_user_operation_start_validation(self):
#        self.assertEqual(
#            self.machine.current_procedure, self.machine.procedures.Initial, "Expected to be in the initial state!"
#        )
#        result = self.process.start_operation("Tertiary", {"OPTION": "b"})
#        time.sleep(0.5)
#        self.assertTrue("errors" not in result, "Expected the start operation to be successful")
