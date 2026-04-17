import logging
import time
import unittest
from itertools import chain
from unittest.mock import MagicMock, patch

import core.api
import tests.api
from core.handlers import StateMachineHandler
from core.state_machine.exceptions import OperationFailedToStart, StateMachineNotRunning
from core.state_machine.procedure import Fallback, Initial, Manual
from core.state_machine.state_machine import StateMachine
from tests.user_operation_machine import (
    Another,
    Constants,
    Continue,
    Final,
    First,
    LongLoop1,
    LongLoop2,
    Loop,
    Next,
    Other,
    StartRecoveryProcedure,
    StartRecoveryProcedure2,
    sm_config,
)

logger = logging.getLogger(__name__)

patch.TEST_PREFIX = (
    "test",
    "setUp",
)


@patch("core.api", new=tests.api.TestApi())
class StateMachineOperations(unittest.TestCase):
    def setUp(self):
        core.api.state = {"test_value": 0.6, "fail_recovery": False}
        core.api.state["NEXT_STEP_DELTA"] = Constants.NEXT_STEP_DELTA
        core.api.state["PREV_STEP_THRESHOLD"] = Constants.PREV_STEP_THRESHOLD
        core.api.state["TARGET_TEMPERATURE"] = Constants.TARGET_TEMPERATURE
        core.api.state["failValidation"] = False
        self.machine = StateMachine(sm_config, start=False)
        self.handler = StateMachineHandler(self.machine)

    def tearDown(self):
        pass

    def test_simple_operation(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        ops = self.machine.get_operations(validate=True)
        self.assertEqual(len(ops), 5, f"Expected 5 ops, got {len(ops)}")
        self.assertEqual(
            ["Manual"],
            [p.name for p in ops[-1].procedures],
            f"Invalid procedure list in ops[-1]. Got {[p.name for p in ops[-1].procedures]}",
        )
        self.assertEqual(
            ["Continue"],
            [p.name for p in ops[0].procedures],
            f"Invalid procedure list in ops[0]. Got {[p.name for p in ops[0].procedures]}",
        )
        self.assertEqual(
            ["First", "Another", "Other", "Final"],
            [p.name for p in ops[1].procedures],
            f"Invalid procedure list in ops[1]. Got {[p.name for p in ops[1].procedures]}",
        )
        self.assertEqual(
            ["First", "Another", "Next"],
            [p.name for p in ops[2].procedures],
            f"Invalid procedure list in ops[2]. Got {[p.name for p in ops[2].procedures]}",
        )
        self.assertEqual(
            ["First", "Another", "Next", "Final"],
            [p.name for p in ops[3].procedures],
            f"Invalid procedure list in ops[3]. Got {[p.name for p in ops[3].procedures]}",
        )

    def test_operations_update_with_current_state(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        result = self.handler.start_operation("NextOperation", {"NEXT_STEP_DELTA": 0.2, "TARGET_TEMPERATURE": 7})
        self.assertTrue(result, "Expected the start operation to be successful")
        while self.machine.current_procedure.name != "Next":
            time.sleep(0.01)
        ops = list(self.machine.get_operations(validate=True))
        self.assertEqual(len(ops), 4, f"Expected to see 4 operations, got {ops}")

    def test_changing_user_operation_in_the_middle_works(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        # First operation 'Continue'
        result = self.handler.start_operation("302bc9f4f03eacda25967f716e986b95", {})
        self.assertTrue(result, "Expected the start operation to be successful")
        n = 0
        while self.machine.current_procedure.name != "Continue" and n < 10:
            n += 1
            time.sleep(0.01)
        self.assertTrue(
            n < 10, f"Expected the state to be found in less than 10 rounds: " f"{self.machine.current_procedure.name}"
        )
        ops = self.machine.get_operations()
        self.assertEqual(len(ops), 2, f"Expected to see two operations in the operation list, got {ops}")
        self.assertTrue(ops[0].static_name == "Final", "Expected to see the Final operation in the second position")
        result = self.handler.start_operation("Final", {})
        self.assertTrue(result, "Expected the start operation to be successful")

    def test_stopping_twice_raises(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        # First operation 'Continue'
        result = self.handler.start_operation("302bc9f4f03eacda25967f716e986b95", {})
        self.assertTrue(result, "Expected the start operation to be successful")
        self.handler.stop(False)
        with self.assertRaises(StateMachineNotRunning):
            self.handler.stop(False)

    def test_start_operation_fails(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")

        # Without include_validations => raise OperationFailedToStart
        with self.assertRaises(OperationFailedToStart):
            result = self.handler.start_operation("Final", {})

        # With include_validations => return serialized Operation
        result = self.handler.start_operation("Final", {}, include_validations=True)
        self.assertIn("valid", result)
        self.assertIn("validations", result)
        self.assertFalse(result["valid"])

    def test_start_operation_fails_parameters(self):
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        core.api.state["failValidation"] = True

        # Without include_validations => raise OperationFailedToStart
        with self.assertRaises(OperationFailedToStart):
            result = self.handler.start_operation("Final", {})

        # With include_validations => return serialized Operation
        result = self.handler.start_operation("Final", {}, include_validations=True)
        self.assertIn("valid", result)
        self.assertIn("validations", result)
        self.assertIn("Validation failed due to parameter value", result["validations"]["procedure_errors"][0])
        self.assertFalse(result["valid"])

    def test_loop_operations(self):
        Next.run = MagicMock()

        # First we run the StateMachine until OperationProcedure
        self.assertEqual(self.machine.current_procedure, Initial, "Expected to be in the initial state!")
        self.handler.start_operation("NextOperation", {"NEXT_STEP_DELTA": 0.2, "TARGET_TEMPERATURE": 7})
        while self.machine.current_procedure.name != "Next":
            time.sleep(0.01)
        self.assertFalse(self.machine.current_operation.running)
        ops = list(self.machine.get_operations(validate=True))
        self.assertEqual(Next.run.call_count, 1)

        # Loop operation is found
        loop_operation = [op for op in ops if op.is_loop][0]
        self.assertTrue(loop_operation)
        loop_operation2 = [op for op in ops if op.is_loop][1]
        self.assertTrue(loop_operation2)
        self.assertEqual(loop_operation2.procedures[0].name, "LongLoop1")
        self.assertEqual(loop_operation2.procedures[1].name, "LongLoop2")

        # Loop operation starts and ends in current procedure
        self.assertEqual(self.machine.current_procedure, loop_operation.start)
        self.assertEqual(self.machine.current_procedure, loop_operation.goal)

        # Loop procedure is the first procedure to run
        self.assertEqual(loop_operation.procedures[0], Loop)
        self.assertTrue(loop_operation.serialize()["operationId"])
        result = self.handler.start_operation(loop_operation.serialize()["operationId"])
        self.assertEqual(result["procedures"][1]["name"], "Loop")

        while self.machine.current_procedure.name != "Next":
            time.sleep(0.01)
        self.assertEqual(self.machine.current_procedure, Next)

        # Check that Next.run is skipped after returning from loop procedure
        self.assertEqual(Next.run.call_count, 1)
        self.assertFalse(self.machine.current_operation.running)

    def test_get_transitions(self):
        self.assertEqual(
            self.machine.get_transitions(),
            [
                (Continue, Final),
                (First, Another),
                (Another, Next),
                (Another, Other),
                (Next, Next),
                (Next, Final),
                (Other, Final),
                (Next, Loop),
                (Loop, Next),
                (Next, LongLoop1),
                (LongLoop1, LongLoop2),
                (LongLoop2, Next),
            ],
        )

    def test_get_procedures(self):
        procedures = self.machine.get_procedures()
        self.assertNotIn(Initial, procedures)
        self.assertNotIn(Manual, procedures)
        self.assertNotIn(Fallback, procedures)
        self.assertEqual(
            procedures,
            {
                Another,
                Continue,
                Final,
                First,
                LongLoop1,
                LongLoop2,
                Loop,
                Next,
                Other,
                StartRecoveryProcedure,
                StartRecoveryProcedure2,
            },
        )

    def test_manual_available(self):
        # procedures has normal procedues and loop procedures
        procedures = self.machine.get_procedures()
        for procedure in procedures:
            ops = self.machine.operations.operations(procedure)
            self.assertTrue(ops, f"Manual not available from {procedure.__name__}")
            self.assertEqual(ops[-1].procedures, [Manual], f"Manual not available from {procedure.__name__}")

        # recovery procedures are not returned as part of the normal graph
        recovery_procedures = list(chain(*(self.machine.operations.recovery_paths)))

        for procedure in recovery_procedures:
            ops = self.machine.operations.operations(procedure)
            self.assertTrue(ops, f"Manual not available from {procedure.__name__}")
            self.assertEqual(ops[-1].procedures, [Manual], f"Manual not available from {procedure.__name__}")
