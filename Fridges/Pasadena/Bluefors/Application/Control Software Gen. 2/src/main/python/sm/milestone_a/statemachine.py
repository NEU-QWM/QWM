import logging
from datetime import timedelta

from core.api import state
from core.device import device
from core.sentinel.config import SentinelConfig, SentryConfig
from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import (
    Initial,
    OperationProcedure,
    Procedure,
    ProcedureError,
    ValidationError,
)

from .sentinel_rules import (
    cooling_water_line,
    cooling_water_line_flow,
    flow_exceptionally_high,
    pressure_for_b1_too_high,
    pressure_for_b1_too_high_error,
    temp_b1_above_100,
)

logger = logging.getLogger(__name__)


class ErrorGroup:
    TEMPERATURE_ERROR = 610
    FLOW_ERROR = 611
    PUMP_ERROR = 612


milestone_parameters = {
    "coolingWaterLimitToStartPumping": "coolingWaterLimitToStartPumping",
    "boosterBasePressureLimit": "boosterBasePressureLimit",
    "boosterPumpingMaxTime": "boosterPumpingMaxTime",
    "boosterStartPressureLimit": "boosterStartPressureLimit",
    "initialValueWaitTime": "initialValueWaitTime",
    "roughPumpingMaxTime": "roughPumpingMaxTime",
    "zeroCirculationFlowLimit": "zeroCirculationFlowLimit"
}


def has_initial_values(state):
    return all([x in state for x in ["COOLING_WATER_TEMPERATURE", "FLOW_VALUE", "P1_PRESSURE", "P2_PRESSURE"]])


class PumpRough(Procedure):
    name = "PumpRough"
    image_url = "images/PPC.mp4"
    penalty = timedelta(hours=2)
    required_parameters = [
        "roughPumpingMaxTime",
        "boosterStartPressureLimit",
        "coolingWaterLimitToStartPumping",
        "zeroCirculationFlowLimit",
    ]

    def validate(self, parameters, state):
        if not has_initial_values(state):
            yield ValidationError(-1, "Initial values not available in state!")

        logger.info(f"PumpRough validate {parameters}")
        logger.info(f'{state["COOLING_WATER_TEMPERATURE"]} and {parameters["coolingWaterLimitToStartPumping"]}')
        if state["COOLING_WATER_TEMPERATURE"] > parameters["coolingWaterLimitToStartPumping"]:
            yield ValidationError(ErrorGroup.TEMPERATURE_ERROR, "Too high cooling water temperature to start pumping")

        if state["FLOW_VALUE"] > parameters["zeroCirculationFlowLimit"]:
            yield ValidationError(ErrorGroup.TEMPERATURE_ERROR, "Too high cooling water temperature to start pumping")

    def enter(self, parameters):
        device.pump_off("R1")
        device.pump_off("B1")
        device.valve_off("V2")
        device.valve_off("V3")

    def procedure(self, parameters):
        logger.info("PumpRough")
        device.valve_off("V2")
        device.valve_on("V3")
        device.pump_on("R1")

        sw = self.stopwatch()
        while sw.elapsed < parameters["roughPumpingMaxTime"]:
            if state["P1_PRESSURE"] < parameters["boosterStartPressureLimit"]:
                return
            self.wait(seconds=1)

        raise ProcedureError(ErrorGroup.PUMP_ERROR, "P1 not low enough after rough-pumping")


class PumpTurbo(Procedure):
    name = "PumpTurbo"
    image_url = "images/Condensing.mp4"
    penalty = timedelta(hours=4)
    required_parameters = ["boosterBasePressureLimit", "boosterPumpingMaxTime", "boosterStartPressureLimit"]

    def validate(self, parameters, state):
        if not has_initial_values(state):
            yield ValidationError(-1, "Initial values not available in state!")

        if state["P1_PRESSURE"] >= parameters["boosterStartPressureLimit"]:
            yield ValidationError(ErrorGroup.PUMP_ERROR, "P1 not low enough to enter PumpTurbo")

    def procedure(self, parameters):
        logger.info("PumpTurbo")
        device.pump_on("B1")
        sw = self.stopwatch()
        while sw.elapsed < parameters["boosterPumpingMaxTime"]:
            if state["P1_PRESSURE"] < parameters["boosterBasePressureLimit"]:
                return
            self.wait(1)

        raise ProcedureError(ErrorGroup.PUMP_ERROR, "P1 not low enough after rough-pumping")


class IdleLowPressure(OperationProcedure):
    name = "IdleLowPressure"
    image_url = "images/Circulation.mp4"
    operation_name = "PumpSystem"
    penalty = timedelta(hours=1)
    required_parameters = ["boosterBasePressureLimit", "boosterStartPressureLimit"]

    def validate(self, parameters, state):
        if not has_initial_values(state):
            yield ValidationError(-1, "Initial values not available in state!")
        if state["P1_PRESSURE"] > parameters["boosterBasePressureLimit"]:
            logger.error("P1 Pressure failed!")
            yield ValidationError(ErrorGroup.PUMP_ERROR, "P1 not low enough to enter IdleLowPressure")

    def procedure(self, parameters):
        logger.info("IdleLowPressure")


class Idle(OperationProcedure):
    name = "Idle"
    operation_name = "StopPumps"
    penalty = timedelta(hours=1)

    def validate_operation(self, from_procedure, operation, parameters, state):
        logger.info(f"Pump R1: {state['R1_ENABLED']} and B1: {state['B1_ENABLED']}")
        # Note that putting simply state['R1'] is not sufficient for the Java side
        if not (state["R1_ENABLED"] or state["B1_ENABLED"]):
            yield ValidationError(-1, "Cannot stop pumps when no pumps are on")

    def procedure(self, parameters):
        logger.info("Idle")
        device.pump_off("R1")
        device.pump_off("B1")


config = StateMachineConfig(
    name="milestone-a",
    transitions=(
        (Initial, PumpRough),
        (PumpRough, PumpTurbo),
        (PumpTurbo, IdleLowPressure),
        (PumpRough, Idle),
        (PumpTurbo, Idle),
        (IdleLowPressure, Idle),
        (Idle, PumpRough),
        (Idle, PumpTurbo),
        (Idle, IdleLowPressure),
    ),
    parameter_mapping=milestone_parameters,
)


sentinel = SentinelConfig(
    [
        temp_b1_above_100,
        pressure_for_b1_too_high,
        pressure_for_b1_too_high_error,
        flow_exceptionally_high,
        cooling_water_line,
        cooling_water_line_flow,
    ]
)


sentry = SentryConfig([])
