import unittest
from unittest.mock import patch, MagicMock

import logging
from datetime import timedelta

from core.device.command import AlertCommand
from core.state_machine.state_machine import StateMachine
from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import Procedure, OperationProcedure, Initial
from core.state_machine.exceptions import ProcedureError, ValidationError

import core.api
import tests.api

logger = logging.getLogger()

patch.TEST_PREFIX = ("test", "setUp")

parameters = {
    "salt_amount": "SALT_AMOUNT",
    "pepper_amount": "PEPPER_AMOUNT",
}
# pepper_amount = Parameter(float, default=Mapping('PEPPER_AMOUNT'))


class Prepare(Procedure):
    name = "Prepare"
    penalty = timedelta(30)

    def procedure(self, parameters):
        logger.info("Prepare.Procedure()")


class Cook(OperationProcedure):
    name = "Cook"
    operation_name = "CookOperation"
    penalty = timedelta(120)
    required_parameters = ["salt_amount", "pepper_amount"]

    def validate(self, parameters, state):
        if not 0 <= parameters["salt_amount"] <= 15:
            yield ValidationError(-1, "Invalid SALT_AMOUNT")
        if not 0 <= parameters["pepper_amount"] <= 1:
            yield ValidationError(-1, "Invalid PEPPER_AMOUNT")
        return True

    def procedure(self, parameters):
        logger.info(
            f"Cook.Procedure() Using salt {parameters.get('salt_amount')} and pepper {parameters.get('pepper_amount')}"
        )
        # i = 0
        # while i < 10:
        # print("Cooking")
        # self.wait(3)
        # i += 1
        if parameters["salt_amount"] == 7:
            raise ProcedureError(-1, "Failed since salt_amount is exactly 7")


class Simmer(OperationProcedure):
    name = "Simmer"
    operation_name = "SimmerOperation"
    penalty = timedelta(240)

    # def idle(self, parameters):
    #    while True:
    #        logging.debug("Simmering in idle state.")
    #        self.wait(timeout=1)

    def procedure(self, parameters):
        logger.info("Cook.Simmer()")


cooker_config = StateMachineConfig(
    name="Cooker",
    transitions=(
        (Initial, Prepare),
        (Prepare, Cook),
        (Cook, Simmer),
    ),
    parameter_mapping=parameters,
)


@patch("core.api", new=tests.api.TestApi())
class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.event_log = core.api.event_log
        self.state = core.api.state
        self.state.clear()
        self.state.update({"SALT_AMOUNT": 10, "PEPPER_AMOUNT": 0.5})
        self.machine = StateMachine(cooker_config, start=True)
        core.api.error = MagicMock()
        core.api.alert = MagicMock()

    def tearDown(self):
        pass

    def find_operation(self, start, procs, goal):
        operations = list(self.machine.get_operations())
        operation = [
            op
            for op in operations
            if op.start.name == start and [p.name for p in op.procedures] == procs and op.static_name == goal
        ]
        self.assertTrue(operation)
        return operation[0]

    def test_it_can_execute_a_valid_operation(self):
        operation = self.find_operation("Manual", ["Prepare", "Cook"], "CookOperation")
        self.machine.run_operation(operation)

    def test_while_running_it_can_run_another_operation(self):
        operation = self.find_operation("Manual", ["Prepare", "Cook", "Simmer"], "SimmerOperation")
        self.machine.run_operation(operation)

        operation = self.find_operation("Simmer", ["Manual"], "Manual")
        self.machine.run_operation(operation)

    def test_it_stores_state_on_running_operation(self):
        operation = self.find_operation("Manual", ["Prepare", "Cook"], "CookOperation")
        self.machine.run_operation(operation)

        logger.info(self.state["currentOperation"])
        op = self.state["currentOperation"]
        currentProcedure = op.get("currentProcedure")
        self.assertEqual(
            currentProcedure,
            "Cook",
            f"Expected the runner to update current operation to state, got {currentProcedure}",
        )

    def test_it_handles_parameters(self):
        operation = self.find_operation("Manual", ["Prepare", "Cook"], "CookOperation")
        self.machine.run_operation(operation, {"salt_amount": 15})

    def test_it_goes_to_manual_mode_on_validation_error(self):
        operation = self.find_operation("Manual", ["Prepare", "Cook"], "CookOperation")
        self.machine.run_operation(operation, {"salt_amount": 20})
        op = self.state["currentOperation"]
        currentProcedure = op.get("currentProcedure")
        self.assertEqual(core.api.alert.call_count, 1)
        self.assertTrue(isinstance(core.api.alert.call_args[0][0], AlertCommand))
        self.assertEqual(
            core.api.alert.call_args[0][0].text,
            "Validation of procedure \"Cook\" failed: Invalid SALT_AMOUNT",
        )
        self.assertEqual(currentProcedure, "Manual", f"Expected state machine to go to Manual, got {currentProcedure}")
        # Also check that Manual mode is persisted to event log
        self.assertEqual(self.event_log[-1]["currentProcedure"], "Manual")

    def test_it_goes_to_manual_mode_on_procedure_error(self):
        operation = self.find_operation("Manual", ["Prepare", "Cook"], "CookOperation")
        self.machine.run_operation(operation, {"salt_amount": 7}, threaded=False)
        op = self.state["currentOperation"]
        currentProcedure = op.get("currentProcedure")

        self.assertEqual(core.api.alert.call_count, 1)
        self.assertTrue(isinstance(core.api.alert.call_args[0][0], AlertCommand))
        self.assertEqual(
            core.api.alert.call_args[0][0].text,
            "Running of procedure \"Cook\" failed: Failed since salt_amount is exactly 7",
        )
        self.assertEqual(currentProcedure, "Manual", f"Expected state machine to go to Manual, got {currentProcedure}")
        self.assertEqual(self.event_log[-1]["currentProcedure"], "Manual")

    def test_multiple_runs_do_not_override_parameters(self):
        operation = self.find_operation("Manual", ["Cook"], "CookOperation")
        self.machine.run_operation(operation, {"salt_amount": 10})

        operation = self.find_operation("Cook", ["Manual"], "Manual")
        self.machine.run_operation(operation)

        operation = self.find_operation("Manual", ["Cook"], "CookOperation")
        self.machine.run_operation(operation, {"salt_amount": 11})

    def test_stop(self):
        self.machine.stop()
        self.assertTrue(self.machine.stopped)
