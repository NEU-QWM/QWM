import logging

from datetime import timedelta

from core.api import state
from core.device import device
from core.state_machine.procedure import (
    Direction, OperationProcedure, Procedure, ProcedureError, ValidationError
)
from sm.general.helpers import Helpers

logger = logging.getLogger(__name__)


class CollectMixtureInitial(Procedure):
    name='Stop circulation and recover most of the helium'
    image_url='images/Collect_mixture.mp4'
    penalty=timedelta(hours=1)
    required_parameters=[
        'mixtureCollectingPressureLimit',
        'initialTankPressure',
        'bypassLN2Trap',
    ]
    direction = Direction.WARMING

    '''
    Sequence: 
    - Turn off circulation turbo pump
    - Open return path to mixture tank, and close EXT LN2 entrance
    - Turn on heatswitches
    - Wait until P5 > ("initialTankPressure"-50mbar)
    - Close return path to mixture tank and open EXT LN2 entrance
    '''

    def validate(self, parameters, state):
        if state['4K_TEMPERATURE'] > 4.6 or state['STILL_TEMPERATURE'] > 5.3:
            yield ValidationError(1649, 'System too warm')
        if state["P5_PRESSURE"] > parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure above initialTankPressure, no need to collect helium")

    def enter(self, parameters):
        self.command_queue.queue_valves_off(["V101",
                                             "V102",
                                             "V104",
                                             "V105",
                                             "V106",
                                             "V107",
                                             "V108",
                                             "V109",
                                             "V110",
                                             "V111",
                                             "V112",
                                             "V113",
                                             "V114",
                                             "V303",
                                             "V306",
                                             "V404",
                                             "V406",])
        device.pump_on("R1A")
        self.command_queue.queue_valves_on(["V502H", "V504H", "V201G", "V001", "V302", "V304"])
        if not parameters["bypassLN2Trap"]:
            self.command_queue.queue_valves_on(["V401"])
        self.command_queue.queue_valves_off(["V403", "V503H", "V501H"])

    def procedure(self, parameters):
        logger.info('Stop circulation')
        Helpers.pump_off_circulation_booster()
        self.wait(2)

        device.valves_off(['V402','V403','V407'])
        device.ln2_trap1_led_off("LED_LN2_TRAP")
        device.valve_on('V005')
        device.heaters_on(['HEATSWITCH_STILL'])
        logger.info('Wait until P5 is greater than initialTankPressure-0.025 or 2 hours has passed')

        sw = self.stopwatch()
        while state['P5_PRESSURE'] < (parameters['initialTankPressure'] - 0.025) and sw.elapsed < 7200:
            # not all collected, continue collecting
            self.wait(5)

        self.wait(1)
        device.valve_off('V005')
        if not parameters["bypassLN2Trap"]:
            device.valves_on(["V402", "V401"])
            device.ln2_trap1_led_on("LED_LN2_TRAP")
        else:
            device.valves_on(["V403"])



class StopCooling(Procedure):
    name='Stop cooling and start recovering helium'
    image_url='images/Collect_mixture.mp4'
    penalty=timedelta(minutes=15)
    required_parameters=[
        'serviceEmptyPressure',
        'coolingStoppingTime',
        'bypassLN2Trap',
    ]
    direction = Direction.WARMING

    def validate(self, parameters, state):
        if state['P6_PRESSURE'] > parameters['serviceEmptyPressure']:
            yield ValidationError(1649, 'Service line pressure P6 too high')
        if not state["PULSE_TUBE_ENABLED"]:
            yield ValidationError(1649, "Pulse tube not running, cannot enter Stop cooling")

    def enter(self, parameters):
        self.command_queue.queue_valves_off(["V101",
                                             "V102",
                                             "V104",
                                             "V105",
                                             "V106",
                                             "V107",
                                             "V108",
                                             "V109",
                                             "V110",
                                             "V111",
                                             "V112",
                                             "V113",
                                             "V114",
                                             "V303",
                                             "V306",
                                             "V404",
                                             "V406",])
        device.pump_on("R1A")
        self.command_queue.queue_valves_on(["V502H", "V504H", "V201G", "V001", "V302", "V304"])
        if not parameters["bypassLN2Trap"]:
            self.command_queue.queue_valves_on(["V401"])
        self.command_queue.queue_valves_off(["V403", "V503H", "V501H"])

    def procedure(self, parameters):

        if state['P1_ENABLED']:
            device.set_cold_cathode('P1')
        self.wait(2)

        device.pump_off("COM")
        device.valve_on("V005")
        device.valves_off(["V402","V403", "V407"])
        device.ln2_trap1_led_off("LED_LN2_TRAP")

        Helpers.pump_off_circulation_booster()
        device.pulse_tube_off('PULSE_TUBE')

        logger.info('Wait for duration of coolingStoppingTime')
        self.wait(parameters['coolingStoppingTime'])


class CollectMixture(Procedure):
    name='Collect helium'
    image_url='images/Collect_mixture.mp4'
    penalty=timedelta(hours=4)
    required_parameters=[
        'mixtureCollectingPressureLimit',
        'collectExtraMixtureTimeLimit',
        'softVacuumCycles',
        'p2PressureLimitMixtureInTank',
        'p4PressureLimitMixtureInTank',
        'collectMixtureTimeLimit',
        'fourKelvinHeaterTemperatureLimit',
        'tankPressureStabilizationTime',
        'pressureStabilizationSqLimit',
        'tankPressureStabilizationMaxTime',
        'initialTankPressure',
        'numberOf4KHeaters',
        'softVacuumWithN2',
        'bypassLN2Trap',
    ]
    direction = Direction.WARMING

    def validate(self, parameters, state):
        if state["PULSE_TUBE_ENABLED"]:
            yield ValidationError(1649, "Pulse tube still running, cannot enter Collect mixture")
        if state["HELIUM_TANK_VALUE"] < 75:
            yield ValidationError(1649, "Open the helium tank manual valve")

    def enter(self, parameters):
        if state["P1_ENABLED"]:
            device.set_cold_cathode("P1")
        self.wait(2)
        device.pulse_tube_off("PULSE_TUBE")
        Helpers.pump_off_circulation_booster()
        device.pump_on("R1A")
        self.command_queue.queue_valves_on(["V502H", "V504H", "V201G", "V001", "V302", "V304", "V005"])
        if not parameters["bypassLN2Trap"]:
            self.command_queue.queue_valves_on(["V401"])
        self.command_queue.queue_valves_off(["V402", "V403", "V407", "V501H", "V503H"])
        device.ln2_trap1_led_off("LED_LN2_TRAP")
        device.pump_off("COM")

    def procedure(self, parameters):
        logger.info('Entering the helium collecting phase')
        logger.info('Checking that condensing pressure drops')
        # Collect until P3_PRESSURE has dropped, or at most collectExtraMixtureTimeLimit seconds
        sw = self.stopwatch()
        while state['P3_PRESSURE'] > parameters['mixtureCollectingPressureLimit'] and \
                sw.elapsed < parameters['collectExtraMixtureTimeLimit']:
            # not all collected, continue collecting
            self.wait(30)

        # Pump cond-side and trap empty
        device.valve_on('V203')

        logger.info('Softening vacuum n times')
        # Soften vacuum N times
        for i in range(parameters['softVacuumCycles']):
            if not parameters["softVacuumWithN2"]:
                device.valve_on('V110')
                self.wait(5)
                device.valve_off('V110')
            else:
                device.valve_on('V111')
                self.wait(5)
                device.valve_off('V111')
            self.wait(5)
            device.valves_on(['V101', 'V104'])
            self.wait(5)
            device.valves_off(['V101', 'V104'])
            self.wait(2)

        # Turn on 4K heaters (fixed power)
        Helpers.warmup_heater_on(parameters)

        # collect rest of mixture
        logger.info('Collecting the rest of the helium')
        # Wait for P2 to drop and P4 to grow
        sw = self.stopwatch()
        #TODO: Break loop if 4K or Still is over 200 K
        while state['P2_PRESSURE'] > parameters['p2PressureLimitMixtureInTank'] \
                or state['P4_PRESSURE'] < parameters['p4PressureLimitMixtureInTank']:
            self.wait(5)
            # check if too much time elapsed
            if sw.elapsed > parameters['collectMixtureTimeLimit']:
                raise ProcedureError(1649, 'Collecting helium taking too long')

            # check 4K flange not too hot
            if state['4K_TEMPERATURE'] > parameters['fourKelvinHeaterTemperatureLimit']:
                Helpers.warmup_heater_off(parameters)
                self.wait(5)

            # pressures low enough for after collection

        # check pressures are stabilized
        previous_p5 = state['P5_PRESSURE']
        logger.info('Wait for checking tank pressure stability')
        self.wait(parameters['tankPressureStabilizationTime'])
        sw = self.stopwatch()
        while (state['P5_PRESSURE'] - previous_p5) ** 2 > parameters['pressureStabilizationSqLimit']:
            previous_p5 = state['P5_PRESSURE']
            logger.info('Updating p5 value for checking tank pressure stability')

            self.wait(parameters['tankPressureStabilizationTime'])
            if sw.elapsed > parameters['tankPressureStabilizationMaxTime']:
                raise ProcedureError(1649, 'Stabilizing tank pressure taking too long')

        if state['P5_PRESSURE'] < parameters['initialTankPressure']:
            raise ProcedureError(1649, 'All helium not pumped back')

        logger.info('Stop pumping')

        for valve in ['V401', 'V502H', 'V203', 'V201G', 'V001', 'V005', 'V302', 'V304']:
            device.valve_off(valve)
            self.wait(10)

        device.pump_off('R1A')


class StopPumping(Procedure):
    name='Stop pumping helium'
    image_url='images/Warmup.mp4'
    penalty=timedelta(minutes=10)
    required_parameters=[
        'initialTankPressure',
        'p2PressureLimitMixtureInTank',
    ]
    direction = Direction.WARMING

    def validate(self, parameters, state):
        if state['P5_PRESSURE'] < parameters['initialTankPressure']:
            yield ValidationError(1649, 'Check helium amount')
        if state['P2_PRESSURE'] > parameters['p2PressureLimitMixtureInTank']:
            yield ValidationError(1649, 'Check helium amount')

    def procedure(self, parameters):
        logger.info('Stopping pumping helium')
        for valve in ['V401', 'V502H', 'V203', 'V201G', 'V001', 'V005', 'V302', 'V304']:
            device.valve_off(valve)
            self.wait(10)

        device.pump_off('R1A')


class WaitUntilWarm(Procedure):
    name='Wait until system warm'
    image_url='images/Warmup.mp4'
    penalty=timedelta(hours=18)
    required_parameters=[
        'stillHeaterTemperatureLimit',
        'fourKelvinHeaterTemperatureLimit',
        'warmupMaxTime',
        'systemWarmTemperature',
        'initialTankPressure',
        'numberOf4KHeaters',
    ]
    direction = Direction.WARMING

    def validate(self, parameters, state):
        if state['STILL_TEMPERATURE'] > parameters['systemWarmTemperature']:
            yield ValidationError(1649, 'System already warm')
        if state['P5_PRESSURE'] < parameters['initialTankPressure']:
            yield ValidationError(1649, 'Check helium amount')

    #TODO Use of queue commands for enter method, close all valves not implemented
    def enter(self, parameters):
        device.pulse_tube_off('PULSE_TUBE')
        device.valves_off([valve for valve in Helpers.all_valves if valve != "V504H"])
        device.pumps_off(Helpers.all_pumps)

    def procedure(self, parameters):
        logger.info('Waiting for STILL_TEMPERATURE to rise above systemWarmTemperature')
        sw = self.stopwatch()
        sw_2 = self.stopwatch()
        Helpers.warmup_heater_on(parameters)
        while state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]:
            self.wait(5)

            if state["4K_TEMPERATURE"] > parameters["fourKelvinHeaterTemperatureLimit"]:
                Helpers.warmup_heater_off(parameters)
                self.wait(60)
                if state["STILL_TEMPERATURE"] < parameters["stillHeaterTemperatureLimit"]:
                    Helpers.warmup_heater_on(parameters)
                    self.wait(30)

            #turn warmup heaters on and off every 3 hours, to prevent timeout in PLC
            if sw_2.elapsed > 10800:
                Helpers.warmup_heater_off(parameters)
                self.wait(5)
                Helpers.warmup_heater_on(parameters)
                self.wait(3)
                #restart stopwatch
                sw_2 = self.stopwatch()

            # Check if too much time has elapsed
            if sw.elapsed > parameters["warmupMaxTime"]:
                Helpers.warmup_heater_off(parameters)
                raise ProcedureError(1649, "System taking too long to warm up")

        Helpers.warmup_heater_off(parameters)
        logger.info("System warmed up")


class IdleWarm(OperationProcedure):
    name='System at room temperature'
    operation_name='Warm up system'
    image_url='images/System_Warm.mp4'
    required_parameters=[
        'systemWarmTemperature',
        'initialTankPressure',
        'numberOf4KHeaters',
]

    def validate_operation(self, from_procedure, operation, parameters, state):
        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

    def validate(self, parameters, state):
        if state['STILL_TEMPERATURE'] < parameters['systemWarmTemperature'] \
                or state['4K_TEMPERATURE'] < parameters['systemWarmTemperature']:
            yield ValidationError(1649, 'System too cold')
        #if state['P5_PRESSURE'] < parameters['initialTankPressure']:
        #        yield ValidationError(-1, 'Check mixture amount')

    def enter(self, parameters):
        logger.info('System at room temperature. Closing all valves.')

        device.valves_off([valve for valve in Helpers.all_valves if valve != "V504H"])
        device.pumps_off(Helpers.all_pumps)
        Helpers.warmup_heater_off(parameters)

    def procedure(self, parameters):
        pass
