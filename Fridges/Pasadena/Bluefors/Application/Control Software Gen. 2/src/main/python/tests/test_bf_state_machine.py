import unittest
from unittest.mock import patch
import time

import logging
from datetime import datetime, timedelta

from core.state_machine.state_machine import StateMachine
from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import Procedure, OperationProcedure, Initial
from core.state_machine.exceptions import ProcedureError

# from core.state_machine import StateMachine, Runner, Router, GlobalParameters, Parameter, Mapping, Process
from core.utils import tznow
import core.api
import tests.api


logger = logging.getLogger()

patch.TEST_PREFIX = ("test", "setUp",)

class Manual(OperationProcedure):
    name = "Manual"
    operation_name = "Manual"

    def procedure(self, parameters):
        logger.info("My manual proc running")


class Stepper(OperationProcedure):
    name = "Stepper"
    operation_name = "Stepper"
    penalty = timedelta(seconds=300)

    def procedure(self, parameters):
        logger.info(f"Stepper function stepping away")


class Stopper(OperationProcedure):
    name = "Stopper"
    operation_name = "Stopper"
    penalty = timedelta(seconds=800)
    priority = 1

    def procedure(self, parameters):
        logger.info(f"Stopper function stepping away")


simplest_state_machine = StateMachineConfig(
    name="simplest", transitions=((Initial, Stepper), (Initial, Stopper)), parameter_mapping={}
)


a_bit_more_involved_state_machine = StateMachineConfig(
    name="a_bit_more",
    transitions=(
        (Initial, Stepper),
        (Initial, Stopper),
        (Stepper, Stopper),
    ),
    parameter_mapping={},
)


@patch("core.api", new=tests.api.TestApi())
class BlueforsStateMachineTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_it_starts_in_manual_mode_by_default(self):
        core.api.state["currentOperation"] = {}
        machine = StateMachine(simplest_state_machine, start=True)
        self.assertEqual(machine.current_procedure.name, "Manual")

    def test_it_can_continue_from_manual(self):
        machine = StateMachine(simplest_state_machine, start=False)
        operations = list(machine.get_operations())
        operation = operations[0]
        self.assertEqual(operation.static_name, "Stopper", "Expected to have Stopper as the first available operation")
        self.assertEqual(len(operation.procedures), 1, "Expected to have Stopper directly from Manual")
        machine.run_operation(operation, threaded=False)
        self.assertEqual(machine.current_procedure.name, "Stopper")

    def test_it_handles_recovery(self):
        core.api.state["currentOperation"] = {
            "uuid": "uu1d",
            "operationId": "8728dceed22309d29a75e4f0d93dfddb",
            "name": "Stepper",
            "procedures": [{"name": "Manual"}, {"name": "Stepper"}],
            "parameters": {},
            "startProcedure": "Manual",
            "currentProcedure": "Stepper",
            "originalStartDatetime": tznow() - timedelta(minutes=30),
            "elapsedTimeInSeconds": 30*60,
        }
        machine = StateMachine(simplest_state_machine, start=True)
        self.assertEqual(
            machine.current_procedure.name, "Stepper", "Expected stepper function to be running after recovery"
        )

    def test_it_handles_failed_recovery(self):
        core.api.state["currentOperation"] = {
            "uuid": "uu1d",
            "operationId": "inv4lid",
            "name": "Stepper",
            "procedures": [{"name": "Manual"}, {"name": "OldStepper"}],
            "parameters": {},
            "startProcedure": "Manual",
            "currentProcedure": "OldStepper",
            "originalStartDatetime": tznow() - timedelta(minutes=30),
            "elapsedTimeInSeconds": 30*60,
        }
        machine = StateMachine(simplest_state_machine, start=True)
        self.assertEqual(
            machine.current_procedure.name, "Manual", "Expected going to Manual mode on failed recovery"
        )

    def test_it_has_one_manual_operation(self):
        machine = StateMachine(a_bit_more_involved_state_machine, start=False)
        ops = [op for op in machine.get_operations() if op.static_name == "Manual"]
        self.assertEqual(len(ops), 1, "Expected only 1 valid manual operation")
        self.assertEqual(ops[0].duration, 0, "Expected manual operations not to have a duration")
