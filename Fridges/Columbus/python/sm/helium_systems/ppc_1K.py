import logging
from datetime import timedelta

from core.api import state
from core.device import device
from core.state_machine.operation import Operation
from core.state_machine.procedure import (
    Direction,
    OperationProcedure,
    Procedure,
    ProcedureError,
    ValidationError,
)
from sm.general.helpers import Helpers

logger = logging.getLogger(__name__)


class EvacuateDilutionRefrigerator(Procedure):
    name="Evacuate dilution refrigerator"
    image_url='images/PPC.mp4'
    penalty=timedelta(minutes=10)
    required_parameters=[
        'pulseTubeCoolingFinalTemperature',
        'turboPumpMaxSpeedStartup',
        'serviceBoosterPumpAvailable',
        'pulseTubeCoolingTargetPressure',
        'initialTankPressure',
    ]

    def validate(self, parameters, state):
        if (state['P1_PRESSURE'] > parameters['pulseTubeCoolingTargetPressure'] or state[
            '50K_TEMPERATURE'] > 85 or
                state['4K_TEMPERATURE'] > 50 or state['STILL_TEMPERATURE'] > 55):
            yield ValidationError(1649, 'System too warm')

    def enter(self, parameters):
        logger.info('Entering EvacuateDilutionRefrigerator')
        Helpers.queue_close_critical_valves(self.command_queue, parameters)

    def procedure(self, parameters):
        # TODO: Put this into enter? Then runner would have to be changed to iterate over enter as an iterator.
        Helpers.pump_off_circulation_booster()
        while Helpers.get_circulation_booster_pump_speed() > parameters['turboPumpMaxSpeedStartup']:
            self.wait(15)

        logger.info('PPC: Evacuate DR: Turn on R1 and valves')
        device.valves_on(['V202', 'V203', 'V502H', 'V504H', 'V001', 'V005', 'V302', 'V304'])
        device.pump_on('R1A')

        self.wait(10)

        # TODO Implement max time
        while state['P3_PRESSURE'] > 0.01 or state['P5_PRESSURE'] < 0.750:
            self.wait(15)

        device.valves_off(['V502H', 'V001'])


class StartCirculation(Procedure):
    name="Start circulation with small amount of helium"
    image_url='images/PPC.mp4'
    penalty=timedelta(minutes=10)
    required_parameters=[
        'pulseTubeCoolingFinalTemperature',
        'pulseTubeCoolingTargetPressure',
        'initialTankPressure',
        "bypassLN2Trap",
    ]
    direction = Direction.COOLING

    #TODO: Enter method with command queue
    def validate(self, parameters, state):
        if (state['P1_PRESSURE'] > parameters['pulseTubeCoolingTargetPressure'] or state[
            '50K_TEMPERATURE'] > 80 or
                state['4K_TEMPERATURE'] > 25 or state['STILL_TEMPERATURE'] > 25):
            yield ValidationError(1649, 'System too warm')
        if state['P3_PRESSURE'] > 0.01:
            yield ValidationError(1649, 'P3 pressure too high')

    def enter(self, parameters):
        logger.info('Entering StartCirculation')

        self.command_queue.queue_valves_off(["V101", "V102", "V104", "V105", "V106",
                                             "V107", "V108",  "V112","V113","V114",
                                             "V303", "V306", "V404", "V406","V501H","V502H",
                                             "V503H"])


        Helpers.queue_pump_off_turbo(self.command_queue, parameters)

        self.command_queue.queue_pumps_off(['B1A', 'B1B', 'B1C'])

        self.command_queue.queue_valves_on(["V204NO", "V205NO", "V206NO"])
    pass

    def procedure(self, parameters):
        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")
        logger.info('Start Circulation: Entering start_circulation()')
        logger.info('Start Circulation: Small amount of helium in circulation')

        device.valve_off('V005')
        device.valves_on(['V403', 'V202', 'V001', 'V302', 'V304'])
        device.pump_on('R1A')

        self.wait(2)

        device.valves_on(['V502H', 'V504H'])

        self.wait(30)

        device.valve_on('V201G')
        device.valve_off('V202')

        self.wait(60)

        # TODO Implement maximum waiting time
        logger.info('Start Circulation: Waiting until t_4K < 4.6, t_still < 5.3')
        while state['4K_TEMPERATURE'] > 4.6 or state['STILL_TEMPERATURE'] > 5.3:
            self.wait(15)


class IdleFourKelvin(OperationProcedure):
    name='4K state'
    image_url='images/4k.mp4'
    operation_name='Cool down to 4K'

    @classmethod
    def display_name(cls, operation: Operation, parameters, state):
        if operation.start.name == "Manual":
            return "Return to 4K state"
        if operation.direction == Direction.COOLING:
            return "Cool down to 4K"
        elif operation.direction == Direction.WARMING:
            return "Warm up to 4K"
        else:
            return "Return to 4K state"

    def validate_operation(self, from_procedure, operation, parameters, state):
        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

    def validate(self, parameters, state):
        if state['4K_TEMPERATURE'] > 4.6 or state['STILL_TEMPERATURE'] > 5.3:
            yield ValidationError(1649, '4K flange, still or mixing chamber temperature too high')
        if state['STILL_TEMPERATURE'] < 2:
            yield ValidationError(1649, 'System colder than 4K state')

    def enter(self, parameters):
        logger.info('Entering IdleFourKelvin')
        #device.queue_valves_off(Helpers.all_valves)
        #device.queue_pumps_off(Helpers.all_pumps)
        pass

    def procedure(self, parameters):
        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")
        logger.info('System at 4K temperature')
