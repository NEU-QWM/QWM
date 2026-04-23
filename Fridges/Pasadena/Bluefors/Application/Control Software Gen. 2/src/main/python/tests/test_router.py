import logging
import unittest
from unittest.mock import patch

from core.state_machine import router
from core.state_machine.operation import Operation
from core.state_machine.procedure import Direction, Initial, Manual, OperationProcedure, Procedure
from core.state_machine.state_machine import StateMachineOperations

logger = logging.getLogger()


class One(Procedure):
    name = "One"


class Two(OperationProcedure):
    name = "Two"
    operation_name = "Two"


class Three(OperationProcedure):
    name = "Three"
    operation_name = "Three"
    priority = -1


class Cooling(Procedure):
    name = "Cooling"
    direction = Direction.COOLING


class Warming(Procedure):
    name = "Warming"
    direction = Direction.WARMING


class RouterTest(unittest.TestCase):
    def test_router_single_op(self):
        graph = ((Initial, One), (One, Two), (Two, One))
        ops = list(router.available_operations(graph, Initial))
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0], Operation([Initial, One, Two]))

        ops = list(router.available_operations(graph, One))
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0], Operation([One, Two]))

    def test_router_two_ops(self):
        graph = ((Initial, One), (One, Two), (Two, One), (One, Three))
        ops = list(router.available_operations(graph, Initial))
        ops = sorted(ops, key=lambda operation: (-operation.priority))

        self.assertEqual(len(ops), 2)
        self.assertEqual(ops[0], Operation([Initial, One, Two]))
        self.assertEqual(ops[1], Operation([Initial, One, Three]))

        ops = list(router.available_operations(graph, One))
        ops = sorted(ops, key=lambda operation: (-operation.priority))
        self.assertEqual(len(ops), 2)
        self.assertEqual(ops[0], Operation([One, Two]))
        self.assertEqual(ops[1], Operation([One, Three]))
        ops = list(router.available_operations(graph, One))

    def test_router_with_manual(self):
        graph = ((Initial, One), (One, Two), (Two, One), (One, Three))
        graph, procedures = StateMachineOperations.inject_manual_procedure(graph, None, None)
        ops = list(router.available_operations(graph, Initial))
        ops = sorted(ops, key=lambda operation: (-operation.priority))
        self.assertEqual(ops[0], Operation([Initial, One, Two]))
        self.assertEqual(ops[1], Operation([Initial, One, Three]))
        self.assertEqual(ops[2], Operation([Initial, Manual]))

    @patch("core.state_machine.router.valid_path", wraps=router.valid_path)
    def test_with_call_count(self, valid_path):
        """
        Test that the early exit from recursion for Initial/Manual procedures
        works as intended.
        """
        graph = ((Initial, One), (One, Two), (Two, One), (One, Three))
        graph, procedures = StateMachineOperations.inject_manual_procedure(graph, None, None)
        _ = list(router.available_operations(graph, Initial))
        self.assertEqual(valid_path.call_count, 7)
        # self.assertEqual(router.find_operations.call_count, 9)

    def test_reverse_routing(self):
        graph = ((Initial, One), (One, Two), (Two, One), (Two, Three))
        operations = list(router.available_operations(graph, Three, reverse=True))
        self.assertEqual(operations[0], Operation([Initial, One, Two, Three]))

    def test_route_direction_filtering(self):
        graph = (
            (Initial, Cooling),
            (Initial, Warming),
            (One, Cooling),
            (One, Warming),
            (Warming, One),
            (Cooling, One),
            (Warming, Two),
            (Cooling, Two),
        )
        # Direction filters out otherwise possible paths:
        # Initial -> Cooling -> One -> Warming -> Two
        # Initial -> Warming -> One -> Cooling -> Two
        operations = list(router.available_operations(graph, Initial))
        self.assertEqual(len(operations), 2)
        self.assertEqual(operations[0], Operation([Initial, Cooling, Two]))
        self.assertEqual(operations[0].direction, Direction.COOLING)
        self.assertEqual(operations[1], Operation([Initial, Warming, Two]))
        self.assertEqual(operations[1].direction, Direction.WARMING)
