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

class IdleEvacuateDRUnit(OperationProcedure):
    name = "Evacuate DR unit"
    image_url = "images/Vacuum_Pump.mp4"
    penalty = timedelta(minutes=60)
    operation_name="Evacuate DR unit"
    required_parameters = [
        "dilutionRefrigeratorEvacuatedPressure",
        "serviceBoosterPumpAvailable",
        "initialTankPressure",
        "pumpDRUnitTime",
        "systemWarmTemperature",
    ]
    direction = Direction.COOLING

    '''
    Sequence:
    - Close all valves, turn off unnecessary pumps
    - Evacuate the DR with B1
    '''

    def validate_operation(self, from_procedure, operation, parameters, state):
        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")


    def validate(self, parameters, state):


        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")
        if (
            state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]
            or state["4K_TEMPERATURE"] < parameters["systemWarmTemperature"]
        ):
            yield ValidationError(1649, "System too cold")

    def enter(self, parameters):
        logger.info("Entering Evacuate DR Unit. Closing all valves.")

        self.command_queue.queue_valves_off(Helpers.all_valves)
        self.command_queue.queue_pumps_off(Helpers.all_pumps)
        self.command_queue.queue_valves_on(["V204NO", "V205NO", "V206NO"])

    def procedure(self, parameters):

        self.evacuateDRUnit(parameters)

        logger.info("Leaving Evacuate DR Unit")


    def evacuateDRUnit(self, parameters):

        # Pump DR with rough pump
        logger.info("EvacuateDR: DR volume empty")

        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            raise ProcedureError(1649,  "P5 pressure below limit, check mixture amount")

        device.valves_off(["V001", "V003", "V004", "V005",
                           "V101", "V102", "V104", "V106", "V107",
                           "V108", "V109","V110","V111","V112", "V114",
                           "V201G", "V202",
                           "V301","V302","V303","V304","V305","V306",
                           "V401", "V402", "V403", "V404", "V405",
                           "V406","V407",
                           "V501H", "V503H"])

        self.wait(2)

        if not state["R2_ENABLED"]:
            device.pump_on("R2")
            self.wait(30)
        else:
            device.pump_on("R2")

        device.valves_on(["V105"])

        logger.info("Pumping service volume until P6_PRESSURE < 1 mbar")

        sw = self.stopwatch()
        while state["P6_PRESSURE"] > 0.001:
            self.wait(2)
            if sw.elapsed > 600:
                raise ProcedureError(1649, "Timeout pumping service volume (P6 volume)")

        self.wait(4)

        device.valves_on(["V203","V502H","V504H"])

        Helpers.pump_on_circulation_booster() # B1A, B1B, B1C

        device.valves_on(["V114","V202","V204NO", "V205NO", "V206NO"])
        self.wait(3)
        device.valves_on(["V201G"])
        self.wait(2)
        device.valves_off(["V202"])

        logger.info(f"Pumping DR unit volume until P3_PRESSURE < {parameters['dilutionRefrigeratorEvacuatedPressure']*1000:.0f} mbar and {parameters['pumpDRUnitTime']/60:.0f} min elapsed")

        sw = self.stopwatch()
        while (state["P3_PRESSURE"] > parameters["dilutionRefrigeratorEvacuatedPressure"]) or (sw.elapsed < parameters["pumpDRUnitTime"]):
            self.wait(2)
            if sw.elapsed > (parameters["pumpDRUnitTime"]+60):
                raise ProcedureError(1649, "Timeout while pumping to DR volume. P3 pressure too high for cooldown")

        # close all valves and pumps
        device.valves_off(Helpers.all_valves)
        device.pumps_off(Helpers.all_pumps)



class PumpRough(Procedure):
    name = "Rough pumping vacuum can"
    image_url = "images/Vacuum_Pump.mp4"
    penalty = timedelta(minutes=30)
    required_parameters = [
        "dilutionRefrigeratorEvacuatedPressure",
        "roughPumpingMaxTime",
        "pumpRoughFinalPressure",
        "serviceBoosterPumpAvailable",
        "turboPumpMaxSpeedStartup",
        "vacuumPressureLimit",
        "initialTankPressure",
    ]
    direction = Direction.COOLING

    '''
    Sequence:
    - Turn on P1 sensor
    - Turn on service pump R2, and open path to VC
    - wait until P1 < "pumpRoughFinalPressure"
    '''


    def validate(self, parameters, state):

        if state["P1_PRESSURE"] < parameters["vacuumPressureLimit"]:
            yield ValidationError(1649, "P1 pressure low, no need to pump VC")
        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")
        if state["P3_PRESSURE"] > parameters["dilutionRefrigeratorEvacuatedPressure"]:
            yield ValidationError(1649, "P3 too large to start cooldown. Evacuate the DR unit volume")

    def enter(self, parameters):
        logger.info("PumpRough: P1 on")

        logger.info("Entering PumpRough. Closing all valves.")

        self.command_queue.queue_valves_off(Helpers.all_valves)
        self.command_queue.queue_pumps_off(Helpers.all_pumps)
        self.command_queue.queue_valves_on(["V204NO", "V205NO", "V206NO"])

    def procedure(self, parameters):


        # Pump VC with rough pump
        logger.info("PumpVacuum: Starting PumpRough")

        self.wait(2)

        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")

        self.wait(2)

        device.pump_on("R2")

        device.valves_on(["V104", "V101", "V105"])

        self.wait(45)

        sw = self.stopwatch()
        while sw.elapsed < parameters["roughPumpingMaxTime"]:
            logger.info("PumpRough in progress, until P1 < pumpRoughFinalPressure")

            if (
                state["P1_PRESSURE"] < parameters["pumpRoughFinalPressure"]
                or state["P6_PRESSURE"] < parameters["pumpRoughFinalPressure"]
            ):
                return
            else:
                self.wait(10)

        raise ProcedureError(1649, "Rough pumping exceeded time limit")



class PumpTurbo(Procedure):
    name = "Pump vacuum can with booster pump"
    image_url = "images/Vacuum_Pump.mp4"
    penalty = timedelta(minutes=30)
    required_parameters = [
        "vacuumPressureErrorTolerance",
        "serviceBoosterPumpAvailable",
        "turboPumpingMaxTime",
        "pumpTurboFinalPressure",
        "pumpRoughFinalPressure",
        "vacuumPressureLimit",
        "initialTankPressure",
    ]
    direction = Direction.COOLING

    '''
    Sequence:
    - Open a pumping path depending on "serviceBoosterPumpAvailable"
    - Wait until P1 < pumpTurboFinalPressure
    '''

    def enter(self, parameters):
        # TODO Uncomment and use methods from helpers
        # self.queue_pump_rough_final_state(parameters)
        # self.queue_pump_on_turbo(parameters)
        Helpers.pump_on_turbo(parameters)
        device.pump_on("R2")
        self.command_queue.queue_valves_on(["V204NO", "V205NO", "V206NO"])

        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")

        if parameters["serviceBoosterPumpAvailable"]:
            device.valves_on(["V101", "V104", "V107", "V106"])
        else:
            device.valves_on(["V101", "V112", "V114", "V105"])

    def validate(self, parameters, state):
        if (
            state["P1_PRESSURE"]
            > parameters["vacuumPressureErrorTolerance"]
            * parameters["pumpRoughFinalPressure"]
        ):
            yield ValidationError(1649, "P1 pressure too high to start turbo pump")
        if state["P1_PRESSURE"] < parameters["vacuumPressureLimit"]:
            yield ValidationError(1649, "P1 pressure low, no need to pump VC")
        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")

    def procedure(self, parameters):
        logger.info("PumpVacuum: Starting PumpTurbo")

        if parameters["serviceBoosterPumpAvailable"]:
            device.valves_on(["V106", "V107"])
            device.valves_off(["V105"])
        else:
            device.valves_on(["V114", "V112"])
            device.valves_off(["V104"])

        Helpers.pump_on_turbo(parameters)

        sw = self.stopwatch()
        logger.info("Pumping VC with booster pump until P1 < pumpTurboFinalPressure")
        while sw.elapsed < parameters["turboPumpingMaxTime"]:

            if state["P1_PRESSURE"] < parameters["pumpTurboFinalPressure"]:
                return
            else:
                self.wait(10)

        raise ProcedureError(1649, "Vacuum can pumping exceeded time limit")


class IdleVacuum(OperationProcedure):
    name = "Vacuum can evacuated"
    image_url = "images/Vacuum_Pump.mp4"
    operation_name = "Evacuate vacuum can"
    required_parameters = [
        "vacuumPressureErrorTolerance",
        "pumpTurboFinalPressure",
        "serviceBoosterPumpAvailable",
        "vacuumPressureLimit",
        "initialTankPressure",
    ]
    direction = Direction.COOLING

    '''
    Sequence:
    - Check that vacuumPressureLimit < P1 < "pumpTurboFinalPressure"
    - Confirm that P5 ~ "initialTankPressure"
    '''


    # def enter(self, parameters):
    # TODO: fix queue method
    #    Helpers.queue_pump_rough_final_state(self, parameters)

    # Helpers.pump_on_turbo()
    def enter(self, parameters):

        device.valves_off([
                           "V102",
                           "V108",
                           "V110",
                           "V111",
                           "V113",
                           "V303",
                           "V306",
                           "V404",
                           "V406",])
        self.wait(2)
        device.pump_on("R2")
        Helpers.pump_on_turbo(parameters)


        if parameters["serviceBoosterPumpAvailable"]:
            device.valves_off(["V105","V112","V114"])
        else:
            device.valves_off(["V001","V104","V106","V107","V201G", "V202"])



    def validate_operation(self, from_procedure, operation, parameters, state):
        if state["P1_PRESSURE"] < parameters["vacuumPressureLimit"]:
            yield ValidationError(1649, "P1 pressure low, no need to pump VC")
        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

    def validate(self, parameters, state):
        if (
            state["P1_PRESSURE"]
            > parameters["vacuumPressureErrorTolerance"]
            * parameters["pumpTurboFinalPressure"]
        ):
            yield ValidationError(1649, "P1 pressure too high")
        if state["P1_PRESSURE"] < parameters["vacuumPressureLimit"]:
            yield ValidationError(1649, "P1 pressure low, no need to pump VC")
        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")

    def procedure(self, parameters):
        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")

        logger.info("Pumping of the vacuum can")
        if parameters['serviceBoosterPumpAvailable']:
            device.valves_on(["V104","V106","V107"])
            logger.info("Wait for B2 pump to reach full speed")
            while state["B2_SPEED"] < 900: #Hz
                self.wait(1)

        else:
            device.valves_on(["V105","V112","V114"])
            logger.info("wait for B1 pump to reach full speed")
            while state["B1A_SPEED"] < 800:
                self.wait(1)
        device.valves_on(["V101"])

        logger.info("Vacuum can evacuated")


class PumpVC(Procedure):
    name="Pump vacuum can"
    operation_name="Pump vacuum can"
    image_url="images/Vacuum_Pump.mp4"
    penalty=timedelta(minutes=60)
    required_parameters = [
        "vacuumPressureErrorTolerance",
        "pumpRoughFinalPressure",
        "pumpTurboFinalPressure",
        "serviceBoosterPumpAvailable",
        "initialTankPressure",
        "systemWarmTemperature",
        "dilutionRefrigeratorEvacuatedPressure",
        "roughPumpingMaxTime",
        "turboPumpMaxSpeedStartup",
        "vacuumPressureLimit",
        "turboPumpingMaxTime",
    ]

    '''
    sequence:
    
    ## Rough pump VC 
    - Close manifold valves
    - Pump VC with rough pump R2
    - Pump until P1 < pumpRoughFinalPressure
    - Skip the rough pumping if P1 < pumpTurboFinalPressure
    
    ## Turbo pump VC 
    - Pump with Turbo
    - Pump until P1 < pumpTurboFinalPressure
  
    '''

    direction = Direction.COOLING

    def validate(self, parameters,state):
        if state["P1_PRESSURE"] < parameters["vacuumPressureLimit"]:
            yield ValidationError(1649, "P1 pressure low, no need to pump VC")
        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")
        if state["P3_PRESSURE"] > parameters["dilutionRefrigeratorEvacuatedPressure"]:
            yield ValidationError(1649, "P3 too large to start cooldown. Evacuate the DR unit volume")

    def enter(self, parameters):
        logger.info("Entering PumpVC. Close service manifold valves.")

        self.command_queue.queue_valves_off(['V101','V102','V104','V105','V106','V107','V108',
                           'V109', 'V110','V111','V112','V113','V114',
                           'V303','V306','V404','V406'])

        self.command_queue.queue_pumps_off(['COM','R1A'])

    def procedure(self, parameters):

        if not state["P1_ENABLED"]:
            device.set_cold_cathode("P1")

        ## PumpRoughVC ###

        if (state["P6_PRESSURE"] > parameters["pumpTurboFinalPressure"] or state["P1_PRESSURE"] > parameters["pumpTurboFinalPressure"]):

            logger.info("Starting PumpRough")

            self.wait(2)

            device.pump_on("R2")
            self.wait(45)
            device.valves_on(["V101","V104","V105"])


            logger.info("PumpRough in progress, and P1 < pumpRoughFinalPressure")
            sw = self.stopwatch()
            while (state["P1_PRESSURE"]) > parameters["pumpRoughFinalPressure"]:
                self.wait(2)
                if sw.elapsed > parameters["roughPumpingMaxTime"]:
                    raise ProcedureError(1649, "Rough pumping exceeded time limit")


        ## PumpTurboVC ###

        Helpers.pump_on_turbo(parameters)

        if state["R2_ENABLED"] == False:
            device.pump_on("R2")
            self.wait(45)

        if parameters["serviceBoosterPumpAvailable"]:
            device.valves_on(["V104","V107", "V106"])
            device.valves_off(["V105"])
        else:
            device.valves_off(["V001","V201G","V202"])
            self.wait(2)
            device.valves_on(["V105", "V114", "V112"])
            device.valves_off(["V104"])

        Helpers.pump_on_turbo(parameters)
        self.wait(5)
        device.valves_on(["V101"])

        sw = self.stopwatch()
        logger.info("Pumping VC with booster pump until P1 < pumpTurboFinalPressure")

        while state["P1_PRESSURE"] > parameters["pumpTurboFinalPressure"]:
            self.wait(10)
            if sw.elapsed > parameters["turboPumpingMaxTime"]:
                raise ProcedureError(1649, "Vacuum can pumping exceeded time limit")

        logger.info("Vacuum can evacuated")






