from __future__ import annotations

from abc import ABC, abstractmethod
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional, Sequence, ClassVar

from core.state_machine.exceptions import ProcedureError, ValidationError

if TYPE_CHECKING:
    from core.state_machine.operation import RunningOperation

# Type hinting
AutomationError = ProcedureError | ValidationError


BOOLEAN_COMMANDS = {"pumpStartStop", "valveOnOff", "heaterOnOff", "pumpStartStop", "turboPumpsStartStop"}


class CS2Error(Enum):
    SENTINEL_ALERT = 1608
    SENTRY_ALERT = 1609
    AUTOMATION_ERROR = 1649


class AlertSeverity(Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"
    INFO = "INFO"


@dataclass
class DeviceCommand:
    device_id: str
    payload: dict
    command_id: str = "command"

    def format(self):
        return {
            "commandId": self.command_id,
            "correlationId": str(uuid.uuid4()),
            "payload": self.payload,
        }

    @property
    def enable(self):
        if self.boolean:
            return next(iter(self.payload.values()))

    @property
    def boolean(self):
        keys = self.payload.keys()
        key = BOOLEAN_COMMANDS.intersection(keys)
        if key and len(keys) == 1:
            return True
        else:
            return False

    @staticmethod
    def pump_on(device_id):
        return DeviceCommand(device_id, {"pumpStartStop": True})

    @staticmethod
    def pump_off(device_id):
        return DeviceCommand(device_id, {"pumpStartStop": False})

    @staticmethod
    def valve_on(device_id):
        return DeviceCommand(device_id, {"valveOnOff": True})

    @staticmethod
    def valve_off(device_id):
        return DeviceCommand(device_id, {"valveOnOff": False})

    @staticmethod
    def heater_on(device_id):
        return DeviceCommand(device_id, {"heaterOnOff": True})

    @staticmethod
    def heater_off(device_id):
        return DeviceCommand(device_id, {"heaterOnOff": False})

    @staticmethod
    def heater_power(heater_device, heater_channel, power):
        return DeviceCommand(
            device_id=heater_device,
            command_id="write",
            payload={"heaters": {str(heater_channel): {"params": {"power": power}}}},
        )

    @staticmethod
    def pulse_tube_on(device_id):
        return DeviceCommand(device_id, {"pulseTubeStartStop": True})

    @staticmethod
    def pulse_tube_off(device_id):
        return DeviceCommand(device_id, {"pulseTubeStartStop": False})

    @staticmethod
    def circulation_turbo_pumps_on(device_id):
        return DeviceCommand(device_id, {"turboPumpsStartStop": True})

    @staticmethod
    def circulation_turbo_pumps_off(device_id):
        return DeviceCommand(device_id, {"turboPumpsStartStop": False})

    @staticmethod
    def set_cold_cathode(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bSetColdCathode": True}},
        )

    @staticmethod
    def ln2_trap1_led_on(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap1Led": True}},
        )

    @staticmethod
    def ln2_trap1_led_off(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap1Led": False}},
        )

    @staticmethod
    def ln2_trap2_led_on(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap2Led": True}},
        )

    @staticmethod
    def ln2_trap2_led_off(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap2Led": False}},
        )

    @staticmethod
    def enable_fse():
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bFSE_Enable": True}},
        )

    @staticmethod
    def disable_fse():
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bFSE_Enable": False}},
        )

    @staticmethod
    def fse_target(target_position):
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"fTargetPosition": target_position}},
        )

    @staticmethod
    def fse_motor_start():
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bMotorStartSW": True}},
        )

    @staticmethod
    def fse_motor_stop(stop):
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bMotorStopSW": stop}},
        )

    @staticmethod
    def enable_fse_fan():
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bFanCMD": True}},
        )

    @staticmethod
    def disable_fse_fan():
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bFanCMD": False}},
        )

    @staticmethod
    def enable_fse_heater():
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bHeaterCMD": True}},
        )

    @staticmethod
    def disable_fse_heater():
        return DeviceCommand(
            device_id="FSE",
            command_id="write",
            payload={"params": {"bHeaterCMD": False}},
        )

    @staticmethod
    def ln2_trap1_led_on(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap1Led": True}},
        )

    @staticmethod
    def ln2_trap1_led_off(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap1Led": False}},
        )

    @staticmethod
    def ln2_trap2_led_on(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap2Led": True}},
        )

    @staticmethod
    def ln2_trap2_led_off(device_id):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"bLnTrap2Led": False}},
        )

    # Magnet power supply commands
    @staticmethod
    def AMI430_set_target_field(device_id, target_field):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureFieldTarget": target_field}}
        )

    @staticmethod
    def AMI430_set_target_current(device_id, target_current):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureCurrentTarget": target_current}}
        )

    @staticmethod
    def AMI430_set_coil_constant(device_id, coil_constant):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureCoilConst": coil_constant}}
        )

    @staticmethod
    def AMI430_ramp_to_zero(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "zero"})

    @staticmethod
    def AMI430_start_ramping(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "ramp"})

    @staticmethod
    def AMI430_pause_ramping(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "pause"})

    @staticmethod
    def AMI430_PSwitch_current(device_id, PSwitch_current):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configurePSwitchCurrent": PSwitch_current}}
        )

    @staticmethod
    def AMI430_PSwitch_ramp_rate(device_id, PSwitch_ramp_rate):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"configurePSwitchPowerSupplyRampRate": PSwitch_ramp_rate}},
        )

    @staticmethod
    def AMI430_PSwitch_heating_time(device_id, PSwitch_heating_time):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"configurePSwitchHeatTime": PSwitch_heating_time}},
        )

    @staticmethod
    def AMI430_PSwitch_cooling_time(device_id, PSwitch_cooling_time):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"configurePSwitchCoolTime": PSwitch_cooling_time}},
        )

    @staticmethod
    def AMI430_PSwitch_cooling_gain(device_id, PSwitch_cooling_gain):
        return DeviceCommand(
            device_id=device_id,
            command_id="write",
            payload={"params": {"configurePSwitchCoolingGain": PSwitch_cooling_gain}},
        )

    @staticmethod
    def AMI430_stability(device_id, stability):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureStability": stability}}
        )

    @staticmethod
    def AMI430_set_current_limit(device_id, current_limit):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureCurrentLimit": current_limit}}
        )

    @staticmethod
    def AMI430_set_voltage_limit(device_id, voltage_limit):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureVoltageLimit": voltage_limit}}
        )

    @staticmethod
    def AMI430_set_PSwitch_ON(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": {"PSwitch": True}})

    @staticmethod
    def AMI430_set_PSwitch_OFF(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": {"PSwitch": False}})

    @staticmethod
    def AMI430_set_number_ramp_rate_segment(device_id, nb_segment):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureRampRateSegments": nb_segment}}
        )

    @staticmethod
    def AMI430_set_quench_detect_rate_variable(device_id, variable):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureQuenchRate": variable}}
        )

    @staticmethod
    def AMI430_set_quenchDetect(device_id, boolean):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureQuenchDetect": boolean}}
        )

    @staticmethod
    def AMI430_set_absorber(device_id, boolean):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureAbsorber": boolean}}
        )

    @staticmethod
    def AMI430_reset_error(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "resetError"})

    @staticmethod
    def AMI430_reset_error(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "resetError"})

    @staticmethod
    def AMI430_opc(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "opc"})

    @staticmethod
    def AMI430_rst(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "rst"})

    @staticmethod
    def AMI430_set_remote(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "systemRemote"})

    @staticmethod
    def AMI430_set_local(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "systemLocal"})

    @staticmethod
    def AMI430_set_ramp_rate_unit(device_id, time_unit):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureRampRateUnits": time_unit}}
        )

    @staticmethod
    def AMI430_set_field_unit(device_id, field_unit):
        return DeviceCommand(
            device_id=device_id, command_id="write", payload={"params": {"configureFieldUnits": field_unit}}
        )

    @staticmethod
    def AMI430_get_idn(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": "idn"})

    @staticmethod
    def AMI430_reset_quench(device_id):
        return DeviceCommand(device_id=device_id, command_id="write", payload={"params": {"quench": False}})

    @staticmethod
    def broadcast_cs2_state(operation: RunningOperation):
        return DeviceCommand(
            device_id="CSSTATE",
            command_id="write",
            payload={
                "params": operation.serialize_to_plc()
            },
        )


@dataclass
class AlertCommand:
    """
    Alerts sent by StateMachine.

    Alert is sent to the Java side using the shared state.
    """

    severity: AlertSeverity
    code: int
    text: str
    title: str

    @classmethod
    def from_error(cls, error: AutomationError, procedure):
        return cls(
            AlertSeverity.ERROR,
            error.code,
            error.prefix.format(procedure.name) + error.message,
            error.title,
        )

    @classmethod
    def from_error_list(cls, errors: Sequence[AutomationError], procedure):
        return cls(
            AlertSeverity.ERROR,
            errors[0].code,
            errors[0].prefix.format(procedure.name) + ", ".join([e.message for e in errors]),
            errors[0].title,
        )

    def format(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "originator": "Automation Statemachine",
            "title": self.title,
            "description": self.text,
        }


@dataclass
class StateMachineError:
    code: int
    text: str
    origin: str = "SM"

    @classmethod
    def from_error(cls, e, procedure):
        return cls(e.code, f"Running of procedure {procedure.name} failed: {e.message}")

    def format(self):
        return {"origin": self.origin, "code": self.code, "message": self.text}


@dataclass(eq=True, frozen=True)
class Alert(ABC):
    """
    Base class for Sentinel/Sentry alerts
    """

    severity: AlertSeverity
    code: int
    text: str = field(compare=False)
    originator: ClassVar[str]
    cs2_error: ClassVar[int]

    def format(self, activation_id="") -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "text": self.text,
            "originator": self.originator,
            "cs2_error_code": self.cs2_error.value,
            "activation_id": activation_id,
        }

    @classmethod
    @abstractmethod
    def from_rule(cls, rule, msg_args) -> "Alert":
        pass


@dataclass(eq=True, frozen=True)
class SentinelAlert(Alert):
    originator = "Sentinel"
    cs2_error = CS2Error.SENTINEL_ALERT

    @classmethod
    def from_rule(cls, rule, msg_args):
        text = rule.msg.format(**msg_args)
        return cls(rule.severity, rule.code, text)


@dataclass(eq=True, frozen=True)
class SentryAlert(Alert):
    execute: Callable
    deprecate: Optional[timedelta]
    originator = "Sentry"
    cs2_error = CS2Error.SENTRY_ALERT

    @classmethod
    def from_rule(cls, rule, msg_args):
        text = rule.msg.format(**msg_args)
        return cls(rule.severity, rule.code, text, rule.execute, rule.deprecate)
