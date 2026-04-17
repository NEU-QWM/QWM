import logging
from datetime import timedelta

from core.api import state
from core.device import device
from core.state_machine.procedure import (
    Direction,
    OperationProcedure,
    Procedure,
    ProcedureError,
    ValidationError
)
from sm.general.helpers import Helpers

logger = logging.getLogger(__name__)


class CollectMixtureInitial(Procedure):
    name = "Stop circulation and recover most of the mixture"
    image_url = "images/Collect_mixture.mp4"
    penalty = timedelta(hours=1)
    required_parameters = [
        "mixtureCollectingPressureLimit",
        "initialTankPressure",
        "bypassLN2Trap",
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
        if state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 5.3:
            yield ValidationError(1649, "System too warm")
        if state["P5_PRESSURE"] > parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure above initialTankPressure, no need to collect mixture")

    def procedure(self, parameters):
        logger.info("Stop circulation")
        Helpers.pump_off_circulation_booster()
        self.wait(2)

        device.valves_off(["V402","V403", "V407"])
        device.ln2_trap1_led_off("LED_LN2_TRAP")
        device.valve_on("V005")
        device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])
        logger.info("Wait until P5 is greater than initialTankPressure-0.05 or 2 hours has passed")

        sw = self.stopwatch()
        while state["P5_PRESSURE"] < (parameters["initialTankPressure"] - 0.05) and sw.elapsed < 7200:
            # not all collected, continue collecting
            self.wait(5)

        self.wait(1)
        device.valve_off("V005")
        if not parameters["bypassLN2Trap"]:
            device.valves_on(["V402", "V401"])
            device.ln2_trap1_led_on("LED_LN2_TRAP")
        else:
            device.valves_on(["V403"])


class StopCoolingCollectMixture(Procedure):
    name = "Stop cooling and recover mixture"
    image_url = "images/Collect_mixture.mp4"
    penalty = timedelta(hours=4)
    required_parameters = ["serviceEmptyPressure",
                           "coolingStoppingTime",
                           "mixtureCollectingPressureLimit",
                           "collectExtraMixtureTimeLimit",
                           "softVacuumCycles",
                           "p2PressureLimitMixtureInTank",
                           "p4PressureLimitMixtureInTank",
                           "collectMixtureTimeLimit",
                           "fourKelvinHeaterTemperatureLimit",
                           "tankPressureStabilizationTime",
                           "pressureStabilizationSqLimit",
                           "tankPressureStabilizationMaxTime",
                           "initialTankPressure",
                           "numberOf4KHeaters",
                           "softVacuumWithN2",
                           "bypassLN2Trap",
                           ]
    direction = Direction.WARMING

    '''
    Sequence: 
    - Turn off P1 sensor
    - Open return path to mixture tank, and close EXT LN2 entrance
    - Turn off circulation turbo pump
    - Turn off pulse tube and still heater
    - Wait for "coolingStoppingTime" (15min)
    - Wait until P3 < "mixtureCollectingPressureLimit" (50mbar)
    - Open V203
    - Soften the vacuum "softVacuumCycles" times
    - Wait until stabilization of P5
    - Close valves and turn off the circulation pump
    '''

    def validate(self, parameters, state):
        if state["P6_PRESSURE"] > parameters["serviceEmptyPressure"]:
            yield ValidationError(1649, "Service line pressure P6 too high")
        if state["STILL_TEMPERATURE"] > 100:
            yield ValidationError(1649, "Tstill above threshold to enter Stop cooling and recover mixture")
        if state["HELIUM_TANK_VALUE"] < 75:
            yield ValidationError(1649, "Open the helium tank manual valve")

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
        self.command_queue.queue_valves_on(["V502H", "V504H", "V201G", "V001", "V302", "V304", "V005"])
        if not parameters["bypassLN2Trap"]:
            self.command_queue.queue_valves_on(["V401"])

        self.command_queue.queue_valves_off(["V402", "V403", "V407", "V501H", "V503H"])
        device.ln2_trap1_led_off("LED_LN2_TRAP")
        device.pump_off("COM")

    def procedure(self, parameters):
        if state["P1_ENABLED"]:
            device.set_cold_cathode("P1")
        self.wait(2)

        device.pump_off("COM")
        device.valve_on("V005")
        device.valves_off(["V402","V403","V407"])
        device.ln2_trap1_led_off("LED_LN2_TRAP")

        Helpers.pump_off_circulation_booster()

        logger.info("Turn off the pulse tube(s)")
        device.pulse_tube_off("PULSE_TUBE")
        device.heater_off("STILL_HEATER")

        logger.info("Wait for duration of coolingStoppingTime")
        self.wait(parameters["coolingStoppingTime"])


        logger.info("Entering the mixture collecting phase")
        logger.info("Checking that condensing pressure drops")
        # TODO: Is this step needed?
        # Collect until P3_PRESSURE has dropped, or at most collectExtraMixtureTimeLimit seconds
        sw = self.stopwatch()
        while (
            state["P3_PRESSURE"] > parameters["mixtureCollectingPressureLimit"]
            and sw.elapsed < parameters["collectExtraMixtureTimeLimit"]
        ):
            # not all collected, continue collecting
            self.wait(30)

        # Pump cond-side and trap empty
        device.valve_on("V203")

        logger.info("Softening vacuum n times")
        # Soften vacuum N times
        for i in range(parameters["softVacuumCycles"]):
            if not parameters["softVacuumWithN2"]:
                device.valve_on("V110")
                self.wait(5)
                device.valve_off("V110")
            else:
                device.valve_on("V111")
                self.wait(5)
                device.valve_off("V111")
            self.wait(5)
            if state["P6_PRESSURE"] < 1.05: # safety: open to VC only if no P6 overpressure
                device.valves_on(["V101", "V104"])
                self.wait(5)
                device.valves_off(["V101", "V104"])
                self.wait(2)
            else:
                logger.info("Overpressure of P6, abort softening of vacuum")
                logger.info("Release overpressure with vent port V110")
                device.valve_on("V110")
                self.wait(5)
                device.valve_off("V110")
                self.wait(2)

        # Turn on 4K heaters (fixed power)
        Helpers.warmup_heater_on(parameters)

        # collect rest of mixture
        logger.info("Collecting the rest of the mixture")
        # Wait for P2 to drop and P4 to grow
        sw = self.stopwatch()
        # TODO: Break loop if 4K or Still is over 200 K
        while (
            state["P2_PRESSURE"] > parameters["p2PressureLimitMixtureInTank"]
            or state["P4_PRESSURE"] < parameters["p4PressureLimitMixtureInTank"]
        ):
            self.wait(5)
            # check if too much time elapsed
            if sw.elapsed > parameters["collectMixtureTimeLimit"]:
                raise ProcedureError(1649, "Collecting mixture taking too long")

            # check 4K flange not too hot
            if state["4K_TEMPERATURE"] > parameters["fourKelvinHeaterTemperatureLimit"]:
                Helpers.warmup_heater_off(parameters)
                self.wait(5)

            # pressures low enough for after collection

        # check pressures are stabilized
        previous_p5 = state["P5_PRESSURE"]
        logger.info("Wait for checking tank pressure stability")
        self.wait(parameters["tankPressureStabilizationTime"])
        sw = self.stopwatch()
        while (state["P5_PRESSURE"] - previous_p5) ** 2 > parameters["pressureStabilizationSqLimit"]:
            previous_p5 = state["P5_PRESSURE"]
            logger.info("Updating p5 value for checking tank pressure stability")

            self.wait(parameters["tankPressureStabilizationTime"])
            if sw.elapsed > parameters["tankPressureStabilizationMaxTime"]:
                raise ProcedureError(1649, "Stabilizing tank pressure taking too long")

        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            raise ProcedureError(1649, "All mixture not pumped back")

        logger.info("Stop pumping")

        for valve in ["V401", "V502H", "V203", "V201G", "V001", "V005", "V302", "V304"]:
            device.valve_off(valve)
            self.wait(10)

        device.pump_off("R1A")



class WaitUntilWarm(Procedure):
    name = "Wait until system warm"
    image_url = "images/Warmup.mp4"
    penalty = timedelta(hours=18)
    required_parameters = [
        "stillHeaterTemperatureLimit",
        "fourKelvinHeaterTemperatureLimit",
        "warmupMaxTime",
        "systemWarmTemperature",
        "initialTankPressure",
        "numberOf4KHeaters",
    ]
    direction = Direction.WARMING

    '''
    Sequence: 
    - Wait until Tstill > "systemWarmTemperature"
    - Turn off 4K heater 
    '''


    def validate(self, parameters, state):
        if state["STILL_TEMPERATURE"] > parameters["systemWarmTemperature"]:
            yield ValidationError(1649, "System already warm")
        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")

    # TODO Use of queue commands for enter method, close all valves not implemented
    def enter(self, parameters):
        device.pulse_tube_off("PULSE_TUBE")
        device.valves_off([valve for valve in Helpers.all_valves if valve != "V504H"])
        device.pumps_off(Helpers.all_pumps)

    def procedure(self, parameters):
        logger.info("Waiting for STILL_TEMPERATURE to rise above systemWarmTemperature")
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
    name = "System at room temperature"
    operation_name = "Warm up system"
    image_url = "images/System_Warm.mp4"
    required_parameters = [
        "systemWarmTemperature",
        "initialTankPressure",
        "numberOf4KHeaters",
    ]

    '''
    Sequence: 
    - Turn off all the valves, pumps and 4K heater
    '''

    direction = Direction.WARMING

    def validate_operation(self, from_procedure, operation, parameters, state):
        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

    def validate(self, parameters, state):
        if (
            state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]
            or state["4K_TEMPERATURE"] < parameters["systemWarmTemperature"]
        ):
            yield ValidationError(1649, "System too cold")


    def enter(self, parameters):
        logger.info("System at room temperature. Closing all valves and turning off devices.")

        device.valves_off([valve for valve in Helpers.all_valves if valve != "V504H"])
        device.pumps_off(Helpers.all_pumps)
        Helpers.warmup_heater_off(parameters)
        device.pulse_tube_off("PULSE_TUBE")

    def procedure(self, parameters):
        pass
