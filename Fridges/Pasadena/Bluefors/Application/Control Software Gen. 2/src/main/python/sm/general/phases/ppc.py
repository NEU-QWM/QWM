from core.device import device
import logging

from datetime import timedelta

from core.state_machine.operation import Operation
from core.state_machine.procedure import (
    Direction,
    OperationProcedure,
    Procedure,
    ProcedureError,
    ValidationError,
)
from core.api import state
from sm.general.helpers import Helpers

logger = logging.getLogger(__name__)


class EvacuateDilutionRefrigerator(Procedure):
    name = "Evacuate dilution refrigerator"
    image_url = "images/PPC.mp4"
    penalty = timedelta(minutes=10)
    required_parameters = [
        "pulseTubeCoolingFinalTemperature",
        "turboPumpMaxSpeedStartup",
        "serviceBoosterPumpAvailable",
        "pulseTubeCoolingTargetPressure",
        "initialTankPressure",
    ]

    '''
    Sequence:
    - Turn off turbo B1, wait for speed to be < "turboPumpMaxSpeedStartup"
    - Turn on circulation pump R1
    - open path to evacuate DR to the P4 volume
    '''

    def validate(self, parameters, state):
        if (
            state["P1_PRESSURE"] > parameters["pulseTubeCoolingTargetPressure"]
            or state["50K_TEMPERATURE"] > 85
            or state["4K_TEMPERATURE"] > 50
            or state["STILL_TEMPERATURE"] > 55
        ):
            yield ValidationError(1649, "System too warm")

    def enter(self, parameters):
        Helpers.queue_close_critical_valves(self.command_queue, parameters)

    def procedure(self, parameters):
        Helpers.pump_off_circulation_booster()
        while Helpers.get_circulation_booster_pump_speed() > parameters["turboPumpMaxSpeedStartup"]:
            self.wait(15)

        logger.info("PPC: Evacuate DR: Turn on R1 and valves")
        device.valves_on(["V202", "V203", "V502H", 'V504H', "V001", "V005", "V302", "V304"])
        device.pump_on("R1A")

        self.wait(10)

        # TODO Implement max time
        while state["P3_PRESSURE"] > 0.01 or state["P5_PRESSURE"] < 0.750:
            self.wait(15)

        device.valves_off(["V502H", "V001"])


class PulsePreCooling(Procedure):
    name="Pulse pre-cooling"
    image_url="images/PPC.mp4"
    penalty=timedelta(hours=1.5)
    required_parameters = [
        "ppcCycleDuration",
        "ppcInletTime",
        "ppcPumpingTime",
        "ppcPressureLimit",
        "turboPumpMaxSpeedStartup",
        "initialTankPressure",
        "pulseTubeCoolingFinalTemperature",
        "pulseTubeCoolingTargetPressure",
        "serviceBoosterPumpAvailable",
    ]
    direction = Direction.COOLING

    '''
    Sequence:
    - Turn off Turbo B1, and wait it to wind down
    - PPC loop
    - Start circulation of a small amount of mixture 
    - Wait until T4 < 4.6 K and Tstill < 5.3 K (6K for FSE system)
    '''

    def validate(self, parameters, state):
        # If the pulse tube is not on, it can be turned on in enter()
        # if state['PULSE_TUBE_ENABLED']:

        if state["P3_PRESSURE"] > 0.01:
            yield ValidationError(1649, "P3 pressure too high")

        if state["STILL_TEMPERATURE"] > 15 or state["4K_TEMPERATURE"] > 15 or state["50K_TEMPERATURE"] > 80:
            yield ValidationError(1649, "System is too warm to run PPC")

        if "FSE" in state:
            if state["STILL_TEMPERATURE"] < 6:
                yield ValidationError(1649, "System already cold enough, no need to run PPC")
        else:
            if state["STILL_TEMPERATURE"] < 5:
                yield ValidationError(1649, "System already cold enough, no need to run PPC")

        if state["HELIUM_TANK_VALUE"] < 75:
            yield ValidationError(1649, "Open the helium tank manual valve")

    def enter(self, parameters):

        self.command_queue.queue_valves_off(["V101", "V102", "V104", "V105", "V106",
                                             "V107","V108", "V112","V113","V114",
                                             "V303", "V306", "V404", "V406","V501H","V502H",
                                             "V503H"])

        self.command_queue.queue_pumps_off(['B1A', 'B1B', 'B1C'])
        Helpers.queue_pump_off_turbo(self.command_queue, parameters)
        device.pump_off("R2")

        Helpers.pump_off_circulation_booster()

        self.command_queue.queue_valves_on(["V005","V202", "V203", "V204NO", "V205NO", "V206NO",
                                            "V302", "V304", "V504H"])

        device.pump_on("R1A")


    def procedure(self, parameters):
        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")

        while Helpers.get_circulation_booster_pump_speed() > parameters["turboPumpMaxSpeedStartup"]:
            logger.info("Waiting for circulation booster pump to slow down...")
            self.wait(15)

        logger.info("PPC: PPC Loop: Entering the main PPC Cycle")

        device.valve_on("V403")

        self.ppc_loop(parameters)

        if state["P3_PRESSURE"] < parameters["ppcPressureLimit"]:
            raise ProcedureError(1649, "Dilution unit blocked")

        self.wait(20)

        logger.info("Start circulation with small amount of mixture")

        device.valve_off("V005")
        device.valves_on(["V403", "V202", "V001", "V302", "V304"])

        self.wait(2)

        device.valves_on(["V502H"])

        self.wait(10)

        device.valve_on("V201G")
        device.valve_off("V202")

        self.wait(10)

        sw = self.stopwatch()
        if "FSE" in state:
            while state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 6:
                self.wait(15)
                if sw.elapsed > 86400: # 24 hours
                    raise ProcedureError(1649, "System not cooling down enough to continue")
        else:
            while state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 5.3:
                self.wait(15)
                if sw.elapsed > 86400: # 24 hours
                    raise ProcedureError(1649, "System not cooling down enough to continue")


    def ppc_loop(self, parameters):
        sw = self.stopwatch()
        while sw.elapsed < parameters["ppcCycleDuration"]:
            device.valves_off(["V001"])
            device.valves_on(["V203"])

            self.wait(parameters["ppcInletTime"])

            device.valves_off(["V203"])
            device.valves_on(["V001"])

            self.wait(parameters["ppcPumpingTime"])

        device.valves_off(["V203", "V403"])
        device.valve_on("V001")





class IdleFourKelvin(OperationProcedure):
    name="4K state"
    image_url="images/4K.mp4"
    operation_name="Cool down to 4K"

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

    '''
    Sequence:
    - Confirm that T4K < 4.6 K and 1.6 K < Tstill < 5.3 K (6K for FSE system)
    '''

    def validate_operation(self, from_procedure, operation, parameters, state):
        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

    def validate(self, parameters, state):
        if "FSE" in state:
            if state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 6:
                yield ValidationError(1649, "System is too warm to start cold insertion of the FSE insert")
        else:
            if state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 5.3:
                yield ValidationError(1649, "System warmer than 4K state")

        if state['STILL_TEMPERATURE'] < 1.6:
            yield ValidationError(1649, "System colder than 4K state")

    def procedure(self, parameters):
        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")
        logger.info("System at 4K temperature")
