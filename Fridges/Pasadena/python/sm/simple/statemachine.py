import logging
from urllib.error import URLError

from core.api import state
from core.device import device
from core.sentinel.config import SentinelConfig, SentryConfig
from core.sentinel.rules import AlertSeverity, SentinelRule
from core.state_machine.config import StateMachineConfig
from core.state_machine.exceptions import ProcedureError, ValidationError
from core.state_machine.procedure import Initial, OperationProcedure, Procedure

logger = logging.getLogger(__name__)

parameters = {
    "heaterPowerOnTemp": "heaterPowerOnTemp",
    "heaterPowerOffTemp": "heaterPowerOffTemp",
}


class LoopProcedure(Procedure):
    name = "Switch traps"

    def procedure(self, parameters):
        self.wait(5)


class ControlLoop(OperationProcedure):
    name = "ControlLoop"
    operation_name = "StartSystem"
    image_url = "images/Circulation.mp4"
    required_parameters = ["heaterPowerOnTemp", "heaterPowerOffTemp"]

    def validate(self, parameters, state):
        if parameters["heaterPowerOnTemp"] > 9000:
            yield ValidationError(1649, "heaterPowerOnTemp should not be above 9000")
        if parameters["heaterPowerOffTemp"] < 2:
            yield ValidationError(1649, "heaterPowerOffTemp should not be below two")

    def _raise_temperature(self, parameters):
        logger.info("raise_temperature started!")
        device.heater_on("SM_SIMPLE_HEATER")
        device.heater_power("SM_SIMPLE_HEATER_DEVICE", 1, 0.5)
        current_temp = state["SM_SIMPLE_TEMPERATURE"]
        while current_temp <= parameters["heaterPowerOffTemp"]:
            logger.info("raise_temperature – check temperature: %f", current_temp)
            yield 1
            current_temp = state["SM_SIMPLE_TEMPERATURE"]

    def _lower_temperature(self, parameters):
        logger.info("lower_temperature started!")
        device.heater_off("SM_SIMPLE_HEATER")
        current_temp = state["SM_SIMPLE_TEMPERATURE"]
        while current_temp >= parameters["heaterPowerOnTemp"]:
            logger.info("lower_temperature – check temperature: %f", current_temp)
            yield 1
            current_temp = state["SM_SIMPLE_TEMPERATURE"]

    def procedure(self, parameters):
        while True:
            if parameters["heaterPowerOnTemp"] == 9000:
                raise ProcedureError(1649, "heaterPowerOnTemp should not be 9000")
            current_temperature = state["SM_SIMPLE_TEMPERATURE"]
            logger.info(
                "Checking procedure entry with %f (%f – %f)",
                current_temperature,
                parameters["heaterPowerOnTemp"],
                parameters["heaterPowerOffTemp"],
            )
            if current_temperature <= parameters["heaterPowerOffTemp"]:
                logger.info("Raise temp!")
                for timeout in self._raise_temperature(parameters):
                    self.wait(timeout)

            elif current_temperature >= parameters["heaterPowerOnTemp"]:
                logger.info("Lower temp!")
                for timeout in self._lower_temperature(parameters):
                    self.wait(timeout)
            else:
                return


config = StateMachineConfig(
    name="simple",
    transitions=((Initial, ControlLoop),),
    parameter_mapping=parameters,
    loop_procedures={ControlLoop: [(LoopProcedure,)]},
)


sentinel = SentinelConfig(
    [
        SentinelRule(
            filter=lambda SM_SIMPLE_TEMPERATURE: SM_SIMPLE_TEMPERATURE > 305,
            severity=AlertSeverity.WARNING,
            code=1101,
            msg="Temperature over limit: {SM_SIMPLE_TEMPERATURE}",
        )
    ]
)


sentry = SentryConfig([])
