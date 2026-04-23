import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from core.state_machine.exceptions import ValidationError
from core.state_machine.procedure import Direction, Initial, Procedure, OperationProcedure
from core.state_machine.operation import Operation, RunningOperation
import tests.api


parameter_mapping = {"first": "f.first", "second": "f.second", "third": "f.third"}
parameters = {"first": 1, "second": 2, "third": 3}


class InvalidProcedure(Procedure):
    name = "Procedure"
    required_parameters = ["first", "second"]

    def validate(self, parameters, state):
        yield ValidationError(-1, "TestProcedureFirstError")
        yield ValidationError(-1, "TestProcedureSecondError")


class InvalidOperationProcedure(OperationProcedure):
    name = "OperationProcedure"
    operation_name = "OperationProcedure"
    required_parameters = ["second", "third"]

    def validate(self, parameters, state):
        yield ValidationError(-1, "TestOperationProcedureFirstError")

    def validate_operation(self, from_procedure, operation, parameters, state):
        yield ValidationError(-1, "TestOperationProcedureFirstOperationError")
        yield ValidationError(-1, "TestOperationProcedureSecondOperationError")


class ValidProcedure(Procedure):
    name = "Procedure"


class SecondValidProcedure(Procedure):
    name = "SecondProcedure"


class ValidOperationProcedure(OperationProcedure):
    name = "OperationProcedure"
    operation_name = "OperationProcedure"


class CoolingOperation(OperationProcedure):
    name = "OperationProcedure"
    operation_name = "OperationProcedure"
    direction = Direction.COOLING


class WarmingOperation(OperationProcedure):
    name = "OperationProcedure"
    operation_name = "WarmingOperation"
    direction = Direction.WARMING


class DisplayNameOperation(OperationProcedure):
    name = "OperationProcedure"
    operation_name = "DisplayNameOperation"
    direction = Direction.WARMING

    @classmethod
    def display_name(cls, operation: Operation, parameters, state) -> None | str:
        return "Custom name"


class ValidOperationTest(unittest.TestCase):
    def test_valid(self):
        operation = Operation([Initial, ValidProcedure, ValidOperationProcedure])
        operation.bind_parameters(parameters, parameter_mapping)
        self.assertTrue(operation.validate())

    def test_invalid_procedure(self):
        operation = Operation([Initial, InvalidProcedure, ValidOperationProcedure])
        operation.bind_parameters(parameters, parameter_mapping)
        procedure_errors, operation_errors = operation._validate()
        self.assertEqual(len(procedure_errors), 2)
        self.assertEqual(len(operation_errors), 0)
        self.assertFalse(operation.validate())

    def test_invalid_operation(self):
        operation = Operation([Initial, ValidProcedure, InvalidOperationProcedure])
        operation.bind_parameters(parameters, parameter_mapping)
        procedure_errors, operation_errors = operation._validate()
        self.assertEqual(len(procedure_errors), 0)
        self.assertEqual(len(operation_errors), 2)
        self.assertFalse(operation.validate())


class OperationTest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = 1200
        self.operation = Operation([Initial, InvalidProcedure, InvalidOperationProcedure])

    def test_parameter_binding(self):
        parameter_mapping = {"first": "f.first", "second": "f.second", "third": "f.third", "fourth": "f.fourth"}
        self.operation.bind_parameters({"first": 1, "second": 2, "third": 3, "fourth": 4}, parameter_mapping)

        # Extra parameters ("fourth") are not bound
        self.assertEqual(self.operation._bound_parameters, {"first": 1, "second": 2, "third": 3})

    def test_operation_direction(self):
        self.assertEqual(Operation([Initial, WarmingOperation]).direction, Direction.WARMING)
        self.assertEqual(Operation([Initial, CoolingOperation]).direction, Direction.COOLING)
        self.assertEqual(Operation([Initial, ValidOperationProcedure]).direction, Direction.NEITHER)
        # Should not happen in real usage, since these are filtered out by router:
        self.assertEqual(Operation([Initial, CoolingOperation, WarmingOperation]).direction, Direction.NEITHER)

    def test_operation_name(self):
        self.assertEqual(Operation([Initial, DisplayNameOperation]).static_name, "DisplayNameOperation")
        self.assertEqual(Operation([Initial, DisplayNameOperation]).dynamic_name(parameters, {}), "Custom name")

    def test_operation_serialize(self):
        self.operation.bind_parameters(parameters, parameter_mapping)
        serialized_operation = self.operation.serialize()
        self.assertEqual(
            serialized_operation,
            {
                "operationId": "2211d7d7e80d3faede894605ed4e1e0a",
                "name": "OperationProcedure",
                "staticName": "OperationProcedure",
                "duration": 0.0,
                "parameters": {
                    "third": {"value": 3, "default": {"mapping": "f.third"}},
                    "second": {"value": 2, "default": {"mapping": "f.second"}},
                    "first": {"value": 1, "default": {"mapping": "f.first"}},
                },
                "procedures": [{"name": "Initial"}, {"name": "Procedure"}, {"name": "OperationProcedure"}],
                "valid": False,
                "validations": {
                    "procedure_errors": ["TestProcedureFirstError", "TestProcedureSecondError"],
                    "operation_errors": [
                        "TestOperationProcedureFirstOperationError",
                        "TestOperationProcedureSecondOperationError",
                    ],
                },
            },
        )

    def test_operation_serialize_no_include_validations(self):
        self.operation.bind_parameters(parameters, parameter_mapping)
        serialized_operation = self.operation.serialize(include_validations=False)
        self.assertEqual(
            serialized_operation,
            {
                "operationId": "2211d7d7e80d3faede894605ed4e1e0a",
                "name": "OperationProcedure",
                "staticName": "OperationProcedure",
                "duration": 0.0,
                "parameters": {
                    "third": {"value": 3, "default": {"mapping": "f.third"}},
                    "second": {"value": 2, "default": {"mapping": "f.second"}},
                    "first": {"value": 1, "default": {"mapping": "f.first"}},
                },
                "procedures": [{"name": "Initial"}, {"name": "Procedure"}, {"name": "OperationProcedure"}],
            },
        )


class RunningOperationTests(unittest.TestCase):
    def test_operations_get_unique_uuid(self):
        operation = Operation([ValidProcedure, ValidOperationProcedure])
        first = RunningOperation.start(operation, {})
        second = RunningOperation.start(operation, {})
        self.assertEqual(first.operation.id, second.operation.id)
        self.assertNotEqual(first.uuid, second.uuid)

    def test_operation_recovery(self):
        procedures = set([ValidProcedure, ValidOperationProcedure])
        procedure_graph = ((ValidProcedure, ValidOperationProcedure),)
        operation = Operation([ValidProcedure, ValidOperationProcedure])
        running_operation = RunningOperation.start(operation, {})
        serialized_operation = running_operation.serialize()
        recovered_operation = RunningOperation.deserialize(serialized_operation, procedures, procedure_graph)
        self.assertTrue(recovered_operation)
        self.assertEqual(recovered_operation.uuid, running_operation.uuid)
        self.assertEqual(recovered_operation, running_operation)

    @patch("core.utils.tznow", return_value=datetime(2000, 1, 1))
    def test_operation_recovery_elapsed_time(self, mock_time):
        """
        After recovery, elapsed time continues counting up from the last value
        """
        procedures = set([ValidProcedure, ValidOperationProcedure])
        procedure_graph = ((ValidProcedure, ValidOperationProcedure),)
        operation = Operation([ValidProcedure, ValidOperationProcedure])
        running_operation = RunningOperation.start(operation, {})

        # runs for 10 seconds
        mock_time.return_value += timedelta(seconds=10)
        serialized_operation = running_operation.serialize()

        # in Fallback mode for 10 seconds
        mock_time.return_value += timedelta(seconds=10)
        recovered_operation = RunningOperation.deserialize(serialized_operation, procedures, procedure_graph)

        # runs for 2 seconds
        mock_time.return_value += timedelta(seconds=2)
        serialized_recovered_operation = recovered_operation.serialize()
        self.assertEqual(serialized_recovered_operation["originalStartDatetime"], datetime(2000, 1, 1))
        self.assertEqual(serialized_recovered_operation["startDatetime"], datetime(2000, 1, 1, 0, 0, 20))
        self.assertEqual(serialized_recovered_operation["elapsedTimeInSeconds"], 12)

    @patch("core.api", new_callable=tests.api.TestApi)
    def test_operation_logging(self, test_api):
        operation = Operation([ValidProcedure, ValidProcedure, SecondValidProcedure, ValidOperationProcedure])
        running_operation = RunningOperation.start(operation, {})
        running_operation.run(None)
        self.assertEqual(len(test_api.event_log), len(operation.procedures) + 1)
        self.assertLessEqual(
            {"currentProcedure": "Procedure", "state": "RUNNING"}.items(), test_api.event_log[0].items()
        )
        self.assertLessEqual(
            {"currentProcedure": "SecondProcedure", "state": "RUNNING"}.items(), test_api.event_log[1].items()
        )
        self.assertLessEqual(
            {"currentProcedure": "OperationProcedure", "state": "RUNNING"}.items(), test_api.event_log[2].items()
        )
        self.assertLessEqual(
            {"currentProcedure": "OperationProcedure", "state": "IDLE"}.items(), test_api.event_log[3].items()
        )
