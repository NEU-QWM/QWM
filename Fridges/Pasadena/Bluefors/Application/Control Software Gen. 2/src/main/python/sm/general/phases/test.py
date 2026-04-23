from datetime import timedelta

from core.state_machine.procedure import OperationProcedure
from sm.general.helpers import Helpers


class TestProcedure(OperationProcedure):
    name = "TestProcedure"
    image_url = "images/PPC.mp4"
    operation_name = "TestProcedure"
    penalty = timedelta(hours=0.1)

    def procedure(self, parameters):
        self.wait(2)
        # device.heater_on('STILL_HEATER')
        # device.heater_power('STILL_HEATING_POWER', 3, 0.008)
        # device.heater_off('4K_HEATER_1_ENABLED')
        Helpers.warmup_heater_on(parameters)
        # device.valves_on(['V104', 'V106', 'V107'])
        self.wait(5)
        Helpers.warmup_heater_off(parameters)
        # self.queue_valves_off(['V104', 'V106', 'V107'])
