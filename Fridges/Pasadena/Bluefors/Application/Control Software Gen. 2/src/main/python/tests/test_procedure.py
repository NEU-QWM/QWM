import unittest
from unittest.mock import patch

from core.state_machine.exceptions import ProcedureError
from core.state_machine.procedure import Procedure

import tests.api

patch.TEST_PREFIX = (
    "test",
    "setUp",
)

class MyProcedure(Procedure):
    name = "Test Procedure"

    def procedure(self, parameters):
        self.command_queue.queue_valves_on(["V001"])

@patch("core.api", new=tests.api.TestApi())
class ProcedureTest(unittest.TestCase):
    def setUp(self):
        pass

    def test_procedure_run_raises_for_queue(self):
        with self.assertRaisesRegex(ProcedureError, "Check that you executed"):
            MyProcedure().run()
