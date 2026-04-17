import unittest
from unittest.mock import patch
from time import sleep

import logging

from core.state_machine.state_machine import StateMachine
from sm.simple.statemachine import config

import core.api
import tests.api

logger = logging.getLogger()
#logging.basicConfig(level=logging.INFO, format='%(name)s %(levelname)s %(message)s')

patch.TEST_PREFIX = ("test", "setUp",)

api = tests.api.TestApi()
@patch("core.api", new=api)
@patch("sm.simple.statemachine.state", new=api.state)
class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.api = core.api
        self.state = core.api.state
        self.state.update({'SM_SIMPLE_TEMPERATURE': -5, 'heaterPowerOnTemp': 0, 'heaterPowerOffTemp': 10})

    def tearDown(self):
        pass

    def find_operation(self, operations, start, procs, goal):
        operation = [
            op for op in operations
            if op.start.name == start and
            [p.name for p in op.procedures] == procs
            and op.static_name == goal
        ]
        self.assertTrue(operation)
        return operation[0]

    def test_it_can_execute_a_valid_operation(self):
        self.machine = StateMachine(config, start=True)
        operations = list(self.machine.get_operations())
        operation = self.find_operation(operations, 'Manual', ['ControlLoop'], 'StartSystem')
        self.machine.run_operation(operation, threaded=True)

        i = 0
        try:
            while i < 10:
                # Increase the sleep time to 1 second if you want to see it switch
                sleep(0.0)
                if self.api.devices['SM_SIMPLE_HEATER']['device_on']:
                    self.api.state['SM_SIMPLE_TEMPERATURE'] += 3
                    self.assertTrue(self.api.devices['SM_SIMPLE_HEATER']['device_on'])
                else:
                    self.api.state['SM_SIMPLE_TEMPERATURE'] -= 3
                    self.assertFalse(self.api.devices['SM_SIMPLE_HEATER']['device_on'])
                i += 1
        finally:
            self.machine.stop()
