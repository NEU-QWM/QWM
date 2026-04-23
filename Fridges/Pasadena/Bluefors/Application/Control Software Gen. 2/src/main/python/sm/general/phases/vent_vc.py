import logging
from datetime import timedelta

from core.api import state
from core.device import device
from core.state_machine.procedure import (
    OperationProcedure,
    Procedure,
    ProcedureError,
    ValidationError,
)
from sm.general.helpers import Helpers

logger = logging.getLogger(__name__)


class VentVacuum(OperationProcedure):
    name="System in atmospheric pressure"
    image_url="images/System_Warm.mp4"
    operation_name="Vent vacuum can"
    required_parameters=[
        "systemWarmTemperature",
        "systemVentedPressure",
        "vacuumPressureLimit",
        "VentWithN2",
        "roughPumpingMaxTime",
        "initialTankPressure",
    ]
    '''
    Sequence:
    - Turn off P1
    - Open path between VC and vent port
    - Wait until P1 and P6 > "systemVentedPressure"
    - Close valves
    - Pump empty the service manifold with R2
    - Pump GHS until P6 < "roughPumpingMaxTime"
    '''
    def validate_operation(self, from_procedure, operation, parameters, state):
        if (
            state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]
            or state["4K_TEMPERATURE"] < parameters["systemWarmTemperature"]
        ):
            yield ValidationError(1649, "System too cold to vent vacuum can")

        if state["PLC_LOCAL_ENABLED"] == True:
            yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

        if state["P1_PRESSURE"] > parameters["systemVentedPressure"]-0.05:
            yield ValidationError(1649, "System already vented")

    def validate(self, parameters, state):
        if (
            state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]
            or state["4K_TEMPERATURE"] < parameters["systemWarmTemperature"]
        ):
            yield ValidationError(1649, "System too cold to vent vacuum can")

        if state["P1_PRESSURE"] > parameters["systemVentedPressure"]-0.05:
            yield ValidationError(1649, "System already vented")

    def enter(self, parameters):
        self.command_queue.queue_valves_off(["V102","V105","V106","V107","V108","V109","V110",
                                             "V111","V112","V113","V114","V303","V306",
                                             "V404","V406"])

    def procedure(self, parameters):
        logger.info("Venting vacuum can")

        if state["P1_ENABLED"]:
            device.set_cold_cathode("P1")

        self.wait(2)

        if parameters["VentWithN2"]:
            device.valves_on(["V111", "V104", "V101"])
        else:
            device.valves_on(["V110", "V104", "V101"])

        sw = self.stopwatch()

        while (
            state["P1_PRESSURE"] < parameters["systemVentedPressure"]
            or state["P6_PRESSURE"] < parameters["systemVentedPressure"]
        ):
            self.wait(2)
            if sw.elapsed > 1200:
                raise ProcedureError(1649, "Vacuum can venting exceeded time limit")

        if parameters["VentWithN2"]:
            device.valves_off(["V111"])
            self.wait(1)
            device.valves_on(["V110"])

        self.wait(15)

        device.valves_off(["V110","V111"])

        # EvacuateGHS service side

        device.valves_off(['V101', 'V102','V106','V107', 'V108', 'V109',
                           'V110', 'V111', 'V112','V113','V114',
                           'V303','V306','V404','V406'])

        if state["P6_PRESSURE"] > 0.001:
            #
            # Pump VC with rough pump
            logger.info("Evacuate GHS: pump service volume empty")

            self.wait(2)

            device.pump_on("R2")

            device.valves_on(["V105", "V104"])

            self.wait(10)

            sw = self.stopwatch()
            logger.info("Pumping service volume until P6_PRESSURE < 1 mbar")
            while state["P6_PRESSURE"] > 0.001:

                if sw.elapsed > parameters["roughPumpingMaxTime"]:
                    raise ProcedureError(1649, "roughPumpingMaxTime limit exceeded")
                self.wait(2)

        device.valves_off(Helpers.all_valves)
        self.wait(1)
        device.pumps_off(Helpers.all_pumps)

