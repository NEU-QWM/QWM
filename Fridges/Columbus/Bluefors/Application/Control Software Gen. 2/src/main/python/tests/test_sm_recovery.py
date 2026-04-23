import logging
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import core.api
import tests.api
from core import utils
from core.state_machine.operation import Operation
from core.state_machine.procedure import Initial
from core.state_machine.state_machine import StateMachine

# from core.api import state
# from core.state_machine import Runner
from tests.user_operation_machine import Another, Constants, Final, First, Next, StartRecoveryProcedure, sm_config

logger = logging.getLogger(__name__)


patch.TEST_PREFIX = (
    "test",
    "setUp",
)


@patch("core.api", new=tests.api.TestApi())
class StateMachineOperationsRecovery(unittest.TestCase):
    def setUp(self):
        self.api = core.api
        self.state = core.api.state
        self.state.clear()
        self.state["test_value"] = 0.6
        self.state["fail_recovery"] = False
        self.state["NEXT_STEP_DELTA"] = Constants.NEXT_STEP_DELTA
        self.state["PREV_STEP_THRESHOLD"] = Constants.PREV_STEP_THRESHOLD
        self.state["TARGET_TEMPERATURE"] = Constants.TARGET_TEMPERATURE
        self.state["failValidation"] = False
        self.op_map = utils.deserialize(
            {
                "uuid": "uu1d",
                "operationId": "0b0c61e36adbc17b99f2a7fa4130a74a",
                "name": "Final",
                "parameters": {
                    "NEXT_STEP_DELTA": Constants.NEXT_STEP_DELTA + 0.1,
                    "PREV_STEP_THRESHOLD": Constants.PREV_STEP_THRESHOLD + 0.1,
                    "TARGET_TEMPERATURE": Constants.TARGET_TEMPERATURE + 0.1,
                    "failValidation": False,
                },
                "procedures": [
                    {"name": "Initial"},
                    {"name": "First", "imageUrl": "/images/start.png"},
                    {"name": "Another", "imageUrl": "/images/50k.png"},
                    {"name": "Next", "imageUrl": "/images/ppc.png"},
                    {"name": "Final", "imageUrl": "/images/final.png"},
                ],
                "startProcedure": "Initial",
                "currentProcedure": "Another",
                "originalStartDatetime": "2023-11-03T14:56:26.551654Z",
                "elapsedTimeInSeconds": 200,
            }
        )
        self.machine = StateMachine(sm_config, start=False)

    def tearDown(self):
        pass

    def test_operations_recover_from_state(self):
        self.op_map["currentProcedure"] = "First"
        running_operation = self.machine.get_recovery_operation(self.op_map)
        self.assertEqual(running_operation.uuid, "uu1d")
        self.assertEqual(running_operation.remaining_procedures(), [First, Another, Next, Final])

        self.op_map["currentProcedure"] = "Next"
        running_operation = self.machine.get_recovery_operation(self.op_map)
        self.assertEqual(running_operation.remaining_procedures(), [Next, Final])

        self.state["currentOperation"] = self.op_map
        self.machine = StateMachine(sm_config, start=True)
        time.sleep(0.1)
        self.assertEqual(self.machine.current_procedure, Final)

        # Check that the system persists old start time
        self.assertEqual(
            self.state["currentOperation"]["originalStartDatetime"].isoformat(), "2023-11-03T14:56:26.551654+00:00"
        )

    def test_alternate_recovery_path(self):
        self.state["fail_recovery"] = True
        running_operation = self.machine.get_recovery_operation(self.op_map)
        self.assertEqual(running_operation.operation, Operation([Initial, StartRecoveryProcedure, Next, Final]))
        self.assertEqual(running_operation.remaining_procedures(), [StartRecoveryProcedure, Next, Final])
        self.assertEqual(running_operation.parameters, self.op_map["parameters"])

    def test_normal_recovery_to_alternate_recovery_path(self):
        self.state["fail_recovery"] = False
        op_map = {
            "uuid": "e1999cb8-a17f-4f43-b131-ad9de4a8dd56",
            "operationId": "6920d2b0b52bcb5964e93ad789b26cd6",
            "name": "Final",
            "startProcedure": "Initial",
            "parameters": {
                "NEXT_STEP_DELTA": 0.2,
                "PREV_STEP_THRESHOLD": 10.1,
                "TARGET_TEMPERATURE": 4.1,
                "failValidation": False,
            },
            "procedures": [
                {"name": "Initial"},
                {"name": "Start Recovery Procedure"},
                {"name": "Next", "imageUrl": "/images/ppc.png"},
                {"name": "Final", "imageUrl": "/images/final.png"},
            ],
            "state": "IDLE",
            "originalStartDatetime": "2024-10-10T07:41:44.898266Z",
            "elapsedTimeInSeconds": 122.44642340000428,
            "currentProcedure": "Final",
        }
        running_operation = self.machine.get_recovery_operation(op_map)
        self.assertEqual(running_operation.operation, Operation([Initial, StartRecoveryProcedure, Next, Final]))
        self.assertEqual(running_operation.remaining_procedures(), [Final])
        self.assertEqual(running_operation.parameters, self.op_map["parameters"])

    def test_recovery_missing_field_in_serialized_operation(self):
        """
        Missing "originalStartDatetime" in the operation map.
        """
        self.state["fail_recovery"] = False
        self.state["NEXT_STEP_DELTA"] = Constants.NEXT_STEP_DELTA
        self.state["PREV_STEP_THRESHOLD"] = Constants.PREV_STEP_THRESHOLD
        self.state["TARGET_TEMPERATURE"] = Constants.TARGET_TEMPERATURE
        op_map = {
            "uuid": "e1999cb8-a17f-4f43-b131-ad9de4a8dd56",
            "operationId": "6920d2b0b52bcb5964e93ad789b26cd6",
            "name": "Final",
            "startProcedure": "Initial",
            "parameters": {
                "NEXT_STEP_DELTA": 0.2,
                "PREV_STEP_THRESHOLD": 10.1,
                "TARGET_TEMPERATURE": 4.1,
                "failValidation": False,
            },
            "procedures": [
                {"name": "Initial"},
                {"name": "Start Recovery Procedure"},
                {"name": "Next", "imageUrl": "/images/ppc.png"},
                {"name": "Final", "imageUrl": "/images/final.png"},
            ],
            "state": "IDLE",
            "elapsedTimeInSeconds": 122.44642340000428,
            "currentProcedure": "Final",
        }
        running_operation = self.machine.get_recovery_operation(op_map)
        self.assertIsNone(running_operation)


@patch("core.api", new=tests.api.TestApi())
class StateMachineOperationsRecoveryBacktracking(unittest.TestCase):
    def setUp(self):
        self.api = core.api
        self.state = core.api.state
        self.state["fail_recovery"] = False
        self.state["failValidation"] = False
        self.op_map = {
            "uuid": "uu1d",
            "operationId": "0b0c61e36adbc17b99f2a7fa4130a74a",
            "name": "Cool",
            "parameters": {
                "NEXT_STEP_DELTA": 0.4,
                "PREV_STEP_THRESHOLD": 5,
                "TARGET_TEMPERATURE": 9,
                "failValidation": False,
            },
            "procedures": [
                {"name": "Initial"},
                {"name": "First", "imageUrl": "/images/start.png"},
                {"name": "Another", "imageUrl": "/images/50k.png"},
                {"name": "Next", "imageUrl": "/images/ppc.png"},
                {"name": "Final", "imageUrl": "/images/final.png"},
            ],
            "startProcedure": "Initial",
            "currentProcedure": "Final",
            "originalStartDatetime": datetime.now(timezone.utc) - timedelta(minutes=30),
            "elapsedTimeInSeconds": 30 * 60,
        }
        self.machine = StateMachine(sm_config, start=False)

    def tearDown(self):
        pass

    def test_operations_recover_and_backtrack(self):
        # Validation of Final should fail, start from Next:
        self.state["test_value"] = 0.4
        running_operation = self.machine.get_recovery_operation(self.op_map)
        self.assertEqual(running_operation.remaining_procedures(), [Next, Final])

        # Validations pass, continue from Final
        self.state["test_value"] = 0.6
        running_operation = self.machine.get_recovery_operation(self.op_map)
        self.assertEqual(running_operation.remaining_procedures(), [Final])
