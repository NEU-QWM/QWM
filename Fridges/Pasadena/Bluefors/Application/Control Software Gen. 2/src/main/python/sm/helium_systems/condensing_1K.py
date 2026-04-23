import logging
from datetime import timedelta
from core.device import device

from core.api import state
from core.state_machine.procedure import Direction, OperationProcedure, Procedure
from core.state_machine.exceptions import ProcedureError, ValidationError
from sm.general.helpers import Helpers

logger = logging.getLogger(__name__)

class Condensing(Procedure):
    name="Condensing"
    image_url='images/Condensing.mp4'
    penalty=timedelta(hours=1.5)
    required_parameters=[
        'initialTankPressure',
        'condensingTriggerHeatswitches',
        'systemBlockedTimer',
        'serviceBoosterPumpAvailable',
        'vacuumPressureLimit',
        'condensingPressureDropMaxTime',
        'condensingPressureDifferenceMaxTime',
        'stillHeatingPower',
        "bypassLN2Trap",
    ]
    direction = Direction.COOLING

    def validate(self, parameters, state):
        #if not state['PULSE_TUBE_ENABLED']:
        #yield ValidationError(-1, 'Pulse tube is not running')
        if not state["P1_ENABLED"]:
            yield ValidationError(1649, "P1 sensor is switched off")
        if state['P1_PRESSURE'] > parameters['vacuumPressureLimit']:
            yield ValidationError(1649, 'Vacuum can pressure is too high')

        if state['4K_TEMPERATURE'] > 25 or state['STILL_TEMPERATURE'] > 25:
            yield ValidationError(1649, 'System too warm to condense')

        if state['P5_PRESSURE'] < 0.015:
            yield ValidationError(1649, 'Helium already in circulation')

        if state["HELIUM_TANK_VALUE"] < 75:
            yield ValidationError(1649, "Open the helium tank manual valve")


    def enter(self, parameters):
        logger.info('Entering Condensing')

        if state["P5_PRESSURE"] < (parameters["initialTankPressure"]*0.95):
            self.command_queue.set_state({"valves": ["V202","V204NO", "V205NO", "V206NO"]})
        else:
            self.command_queue.set_state({"valves": ["V204NO", "V205NO", "V206NO"]})

        device.heater_off("STILL_HEATER")
        device.heater_off("MXC_HEATER")

    def procedure(self, parameters):
        logger.info("Initializing condensing")
        self.initialize_condensing(parameters)

        heat_switch_trigger_pressure = state['P5_PRESSURE'] - parameters['condensingTriggerHeatswitches']

        if state['P5_PRESSURE'] > 0.09:
            logger.info('Condensing: Condensing High P5: Entering the P5 > 90 mbar valve V003 condensing loop')
            sw_high_pressure = self.stopwatch()
            while state['P5_PRESSURE'] > 0.09:
                self.iterate_high_pressure_condensing_loop(parameters, heat_switch_trigger_pressure)
                if sw_high_pressure.elapsed > 18000: # 5h
                    logger.info("Condensing too long")
                    logger.info("Leave system in a safe circulation state")

                    device.valve_off("V003")
                    device.valve_on("V001")

                    device.pump_off("COM")
                    device.valves_off(["V503H", "V003", "V004"])

                    logger.info("Turning on V202, V203, V502H, V005")
                    device.valves_on(["V202", "V203", "V502H", "V005"])

                    self.wait(10)

                    logger.info("Turning off valve V501H")
                    device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture
                    raise ProcedureError(1649, "Condensing timeout during the high pressure sequence")

            device.valve_off('V003')
            device.valve_on('V001')

        logger.info('CondensingLowPressure: Entering the P5 > 50 valve V004 condensing loop')

        while state['P5_PRESSURE'] > 0.010:
            self.iterate_low_pressure_condensing_loop(parameters, heat_switch_trigger_pressure)

        device.valve_off('V004')
        device.valve_on('V001')

        ###
        logger.info("Enter CondensingFinalization")

        logger.info('CondensingFinalization: Entering CondensingFinalization')
        logger.info('CondensingFinalization: Tank pressure below 10 mbar, pump remaining gas into circulation')
        device.heater_off('HEATSWITCH_STILL')
        device.valve_on('V004')
        self.wait(180)

        device.valve_off('V001')
        self.wait(180)

        device.valve_off('V004')
        device.valve_on('V001')
        self.wait(60)

        logger.info('CondensingFinalization: Starting normal circulation')
        device.pump_off('COM')

        # Wait for P3_PRESSURE to be under 1.0
        sw = self.stopwatch()
        while state['P3_PRESSURE'] > 1.000:
            self.wait(2)

            if sw.elapsed > parameters['condensingPressureDropMaxTime']:
                raise ProcedureError(1649, 'Condensing pressure not dropping')

        # Wait for P4_PRESSURE to be under P3_PRESSURE
        device.valves_off(['V501H', 'V503H'])
        self.wait(2)

        sw = self.stopwatch()
        while state['P4_PRESSURE'] > state['P3_PRESSURE']:
            self.wait(2)

            if sw.elapsed > parameters['condensingPressureDifferenceMaxTime']:
                raise ProcedureError(1649, 'P3-P4 pressure difference not decreasing')

        # Wait for P3_PRESSURE to drop below 0.9
        device.valve_on('V502H')
        self.wait(180)

        sw = self.stopwatch()
        while state['P3_PRESSURE'] > 0.900:
            self.wait(5)

            if sw.elapsed > parameters['condensingPressureDropMaxTime']:
                raise ProcedureError(1649, 'P3 pressure not dropping, turbo pump cannot be started')

        Helpers.pump_on_circulation_booster()
        self.wait(60)

        logger.info('System cooling to base temperature')

    def initialize_condensing(self, parameters):
        if state['P5_PRESSURE'] < parameters['initialTankPressure'] - 0.05:
            device.heaters_off(['HEATSWITCH_STILL'])
        else:
            device.heaters_on(['HEATSWITCH_STILL'])

        Helpers.pump_off_circulation_booster()

        while Helpers.get_circulation_booster_pump_speed() > 50:
            logger.info('Waiting for circulation booster pump to slow down')
            self.wait(15)

        Helpers.close_critical_valves(parameters)

        logger.info('Condensing: Condensing Init: Initializing circulation')
        if not parameters["bypassLN2Trap"]:
            device.valves_on(['V501H', 'V503H', 'V504H', 'V401', 'V402', 'V302', 'V304'])
        else:
            device.valves_on(['V501H', 'V503H', 'V504H', 'V403', 'V302', 'V304'])
        device.ln2_trap1_led_on("LED_LN2_TRAP")
        device.pumps_on(['COM'])

        Helpers.pump_on_circulation_pump_R1(parameters)

        self.wait(10)

        device.valves_on(['V202', 'V001'])

        self.wait(60)

        device.valve_on('V201G')
        device.valve_off('V202')

    def iterate_high_pressure_condensing_loop(self, parameters, heat_switch_trigger_pressure):
        """
        Auxiliary method containing the logic for the main loop iterated during CondensingHighPressure.
        Using valves V001 and V003, we first have P4_PRESSURE be over 0.9, and after that wait until it goes below 0.6.
        """
        device.valve_on('V003')
        device.valve_off('V001')

        # First we wait for P4_PRESSURE to be over 0.9
        sw = self.stopwatch()
        while state['P4_PRESSURE'] < 0.900:
            self.wait(0.5)

            if sw.elapsed > 180:
                # If P4_PRESSURE did not grow fast enough, raise an error

                device.valve_off('V003')
                device.valve_on('V001')

                if state['P5_PRESSURE'] > 0.200:
                    logger.info("Error in condensing: P4 doesn't increase fast enough")
                    logger.info("Leave system in a safe state, recovering mixture")
                    device.pump_off("COM")
                    device.valves_off(["V503H", "V003", "V004", "V403", "V402", "V407"])

                    logger.info("Turning on V202, V203, V502H, V005")
                    device.valves_on(["V202", "V203", "V502H", "V005"])

                    self.wait(10)

                    logger.info("Turning off valve V501H")
                    device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture
                    raise ProcedureError(1649, 'Needle valve set too tight, check adjustment')
                else:
                    break


        # Now we are above 900 mbar, so we'll stop mixture intake from the tank

        # Toggle these valves so that P4_PRESSURE is being lowered
        device.valve_off('V003')
        device.valve_on('V001')

        # Reset stopwatch
        sw = self.stopwatch()

        self.wait(10)

        # Evaluate if heat switches can be turned off:

        if state['HEATSWITCH_STILL_ENABLED'] and state['P5_PRESSURE'] < heat_switch_trigger_pressure \
            and state['STILL_TEMPERATURE'] < (state['4K_TEMPERATURE'] + 0.7):
            device.heater_off('HEATSWITCH_STILL')

        # Then wait for P4_PRESSURE to be under 0.6
        while state['P4_PRESSURE'] > 0.600:
            self.wait(2)

            if sw.elapsed > parameters['systemBlockedTimer']:  # TODO Verify that this comparison is ok
                # If P4_PRESSURE did not decrease fast enough, raise an error

                logger.info("Error in condensing: P4 doesn't decrease fast enough")
                logger.info("Leave system in a safe state, recovering mixture. Turning off COM (helium compressor) and valves V503H, V402, V403, V407")
                device.pump_off('COM')
                device.valves_off(['V503H', 'V403', 'V402', 'V407'])

                logger.info("Turning on V202, V203, V502H, V005")
                device.valves_on(['V202', 'V203', 'V502H', 'V005'])

                self.wait(10)

                logger.info("Turning off valve V501H")
                device.valve_off('V501H')  # Could be appended with a procedure to collect all condensed mixture

                raise ProcedureError(1649, 'System not condensing, check system manual for troubleshooting')

        # If the pressure decreased enough, we can go to the next procedure

    def iterate_low_pressure_condensing_loop(self, parameters, heat_switch_trigger_pressure):
        """
        Auxiliary method containing the logic for the main loop iterated during CondensingLowPressure.
        Using valves V001 and V004, we first have P4_PRESSURE be over 0.9, and after that wait until it goes below 0.6.
        """
        sw = self.stopwatch()
        # Evaluate if heat switches can be turned off:
        if state['HEATSWITCH_STILL_ENABLED'] and state['STILL_TEMPERATURE'] < 4 \
            and state['STILL_TEMPERATURE'] < (state['4K_TEMPERATURE'] + 0.1):
            device.heater_off('HEATSWITCH_STILL')

        device.valve_on('V004')
        device.valve_off('V001')

        # First we wait for P4_PRESSURE to be over 0.9 bar, at most 60 seconds
        loop_sw = self.stopwatch()
        while state['P4_PRESSURE'] < 0.900 and loop_sw.elapsed < 60:
            self.wait(0.5)

        # Toggle these valves so that P4_PRESSURE is being lowered again
        device.valve_on('V001')
        device.valve_off('V004')

        self.wait(2)

        # And wait for P4_PRESSURE to be under 0.6
        while state['P4_PRESSURE'] > 0.600:
            self.wait(2)

            if sw.elapsed > parameters['systemBlockedTimer']:
                # If P4_PRESSURE did not decrease fast enough, raise an error

                logger.info('CondensingHighPressure — Error: Leave system in a safe state, recovering helium. '
                            'Turning off COM (helium compressor) and valves V503H, V402, V403, V407')
                device.pump_off('COM')
                device.valves_off(['V503H', 'V402', 'V403', 'V407'])

                logger.info('Condensing: Condensing High P5 — Error: Turning on V202, V203, V502H, V005')
                device.valves_on(['V202', 'V203', 'V502H', 'V005'])

                self.wait(10)

                logger.info('Condensing: Condensing High P5 — Error: Turning off valve V501H')
                device.valve_off('V501H')  # Could be appended with a procedure to collect all condensed mixture

                raise ProcedureError(1649, 'System not condensing, check the system manual')

        # Evaluate if heat switches can be turned off:
        if state['HEATSWITCH_STILL_ENABLED'] and state['STILL_TEMPERATURE'] < 4 \
            and state['STILL_TEMPERATURE'] < (state['4K_TEMPERATURE'] + 0.1):
            device.heater_off('HEATSWITCH_STILL')


class IdleCirculating(OperationProcedure):
    name='System in circulation mode'
    image_url='images/Circulation.mp4'
    operation_name='Cool down'
    required_parameters=[
        'bypassLN2Trap',
        'stillHeatingPower',
    ]

    def validate_operation(self, from_procedure, operation, parameters, state):
        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

    def validate(self, parameters, state):
        if state['P5_PRESSURE'] > 0.020:
            yield ValidationError(1649, 'Ready for condensing finalization')
        if state['4K_TEMPERATURE'] > 4.2 or state['STILL_TEMPERATURE'] > 2:
            yield ValidationError(1649, '4K flange or Still flange temperature too high')
        if state["HELIUM_TANK_VALUE"] < 75:
            yield ValidationError(1649, "Open the helium tank manual valve")


    def enter(self, parameters):
        device.pulse_tube_on("PULSE_TUBE")
        device.heaters_off(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])
        self.command_queue.queue_valves_off(['V003','V004', 'V005','V112','V113',
                                             'V114','V202','V203','V301',
                                             'V303', 'V305','V306','V404',
                                             'V405','V406', 'V407','V503H','V501H'])

        if not parameters["bypassLN2Trap"]:
            self.command_queue.queue_valves_off(["V403"])
        else:
            self.command_queue.queue_valves_off(["V401", "V402", "V405", "V407"])

        device.pumps_off(['COM'])
        self.wait(1)
        if state['V201G_ENABLED'] == False:
            device.valves_on(['V202'])
            self.wait(5)
            device.valves_on(['V201G'])
            self.wait(1)
            device.valves_off(['V202'])
        if not parameters["bypassLN2Trap"]:
            self.command_queue.queue_valves_on(['V001','V204NO', 'V205NO', 'V206NO',
                                                'V302', 'V304', 'V402', 'V401', 'V502H', 'V504H'])
        else:
            self.command_queue.queue_valves_on(['V001','V204NO', 'V205NO', 'V206NO',
                                                'V302', 'V304', 'V403', 'V502H', 'V504H'])
        device.pumps_on(['R1A'])
        Helpers.pump_on_circulation_booster()

        device.heater_on("STILL_HEATER")
        device.heater_power("STILL_HEATING_POWER", 3, parameters["stillHeatingPower"])

    def procedure(self, parameters):
        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")
        logger.info("System in circulation mode")
