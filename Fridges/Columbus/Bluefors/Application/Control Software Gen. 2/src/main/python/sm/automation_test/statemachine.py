from datetime import timedelta

import core.api
from core.device import device
from core.device.command import AlertCommand, AlertSeverity
from core.sentinel.config import SentinelConfig, SentryConfig
from core.sentinel.rules import ParameterizedSentinelRule, SentinelRule, SentryRule
from core.state_machine.config import StateMachineConfig
from core.state_machine.exceptions import ProcedureError, ValidationError
from core.state_machine.procedure import Initial, Manual, OperationProcedure

from .loop_procedures import Loop, LongLoop1, LongLoop2
from .mock_procedures import (
    MockCollectMixture,
    MockCollectMixtureInitial,
    MockCondensingFinalization,
    MockCondensingHighPressure,
    MockCondensingLowPressure,
    MockEvacuateGHS,
    MockIdleCirculating,
    MockIdleFourKelvin,
    MockIdleVacuum,
    MockIdleWarm,
    MockPulsePreCooling,
    MockPulseTubeCooling,
    MockPulseTubeCoolingFinalization,
    MockPulseTubeCoolingFinalizationWithoutPPC,
    MockPumpRough,
    MockPumpTurbo,
    MockStopCooling,
    MockStopVacuumPumping,
    MockVentVacuum,
    MockWaitUntilWarm,
)


class ParameterizedSentinelWarningProcedure(OperationProcedure):
    name = "Parameterized Sentinel Warning"
    operation_name = "Parameterized Sentinel Warning"
    priority = 90
    penalty = timedelta(seconds=2)


class SentinelWarningProcedure(OperationProcedure):
    name = "Sentinel Warning"
    operation_name = "Sentinel Warning"
    priority = 100
    penalty = timedelta(seconds=1)


class SentinelErrorProcedure(OperationProcedure):
    name = "Sentinel Error"
    operation_name = "Sentinel Error"
    priority = 100


class SentryActionProcedure(OperationProcedure):
    name = "Sentry Open Valve"
    operation_name = "Sentry Open Valve"
    priority = 50


class SentinelGraphWarningProcedure(OperationProcedure):
    name = "Sentinel Graph Warning"
    operation_name = "Sentinel Graph Warning"
    priority = 10


class ActiveIdleProcedure(OperationProcedure):
    name = "Active Idle"
    operation_name = "Active Idle"

    def idle(self, parameters):
        while True:
            core.api.alert(AlertCommand(AlertSeverity.INFO, 1649, "Automation idling", "Automation notification"))
            self.wait(10)


class ValidationErrorProcedure(OperationProcedure):
    name = "Validation Error Procedure"
    operation_name = "Validation Error Procedure"
    priority = 1

    def validate(self, parameters, state):
        if self.operation is not None:
            yield ValidationError(1649, "Validation for this Procedure always fails")


class ProcedureErrorProcedure(OperationProcedure):
    name = "Procedure Error Procedure"
    operation_name = "Procedure Error Procedure"
    priority = 1

    def procedure(self, parameters):
        raise ProcedureError(1649, "Running this Procedure always fails")


config = StateMachineConfig(
    name="automation-test",
    transitions=(
        (Initial, SentinelErrorProcedure),
        (Initial, SentinelWarningProcedure),
        (Initial, ActiveIdleProcedure),
        (Initial, ParameterizedSentinelWarningProcedure),
        (Initial, ValidationErrorProcedure),
        (Initial, ProcedureErrorProcedure),
        (Initial, SentinelGraphWarningProcedure),
        (SentinelWarningProcedure, SentinelErrorProcedure),
        (SentinelWarningProcedure, SentryActionProcedure),
        (MockIdleWarm, MockVentVacuum),
        (MockVentVacuum, MockEvacuateGHS),
        (MockEvacuateGHS, MockIdleWarm),
        (Initial, MockPumpRough),
        (MockIdleWarm, MockPumpRough),
        (MockPumpRough, MockPumpTurbo),
        (MockPumpTurbo, MockIdleVacuum),
        (MockIdleVacuum, MockPulseTubeCooling),
        (MockPulseTubeCooling, MockStopVacuumPumping),
        (MockStopVacuumPumping, MockPulseTubeCoolingFinalization),
        (MockPulseTubeCoolingFinalization, MockPulseTubeCoolingFinalizationWithoutPPC),
        (MockPulseTubeCoolingFinalizationWithoutPPC, MockIdleFourKelvin),
        (MockPulseTubeCoolingFinalization, MockPulsePreCooling),
        (MockPulsePreCooling, MockIdleFourKelvin),
        (MockIdleFourKelvin, MockCondensingHighPressure),
        (MockCondensingHighPressure, MockCondensingLowPressure),
        (MockCondensingLowPressure, MockCondensingFinalization),
        (MockCondensingFinalization, MockIdleCirculating),
        (MockIdleCirculating, MockCollectMixtureInitial),
        (MockCollectMixtureInitial, MockIdleFourKelvin),
        (MockIdleCirculating, MockStopCooling),
        (MockStopCooling, MockCollectMixture),
        (MockCollectMixture, MockWaitUntilWarm),
        (MockWaitUntilWarm, MockIdleWarm),
        (MockPumpRough, MockIdleWarm),
        (MockPumpTurbo, MockIdleWarm),
        (MockIdleVacuum, MockIdleWarm),
        (MockPulseTubeCooling, MockWaitUntilWarm),
        (MockStopVacuumPumping, MockWaitUntilWarm),
        (MockPulseTubeCoolingFinalization, MockWaitUntilWarm),
        (MockPulseTubeCoolingFinalizationWithoutPPC, MockWaitUntilWarm),
        (MockIdleFourKelvin, MockStopCooling),
        (MockCondensingHighPressure, MockStopCooling),
        (MockCondensingLowPressure, MockStopCooling),
        (MockCondensingFinalization, MockStopCooling),
    ),
    loop_procedures={
        Manual: [(Loop,), (LongLoop1, LongLoop2)],
        SentinelWarningProcedure: [(LongLoop1, LongLoop2)],
    },
    parameter_mapping={"persistenceMaxTimeout": "persistenceMaxTimeout"},
)


sentinel = SentinelConfig(
    [
        SentinelRule(
            filter=lambda: True,
            severity=AlertSeverity.ERROR,
            code=1001,
            msg="Sentinel Error Procedure entered",
            applies_in_procedures=["Sentinel Error"],
        ),
        SentinelRule(
            filter=lambda V3_ENABLED: V3_ENABLED,
            severity=AlertSeverity.ERROR,
            code=1002,
            msg="Manual Procedure: V3 should not be enabled",
            applies_in_procedures=["Manual"],
        ),
        SentinelRule(
            filter=lambda: True,
            severity=AlertSeverity.WARNING,
            code=1003,
            msg="Sentinel Warning Procedure entered",
            applies_in_procedures=["Sentinel Warning"],
        ),
        ParameterizedSentinelRule(
            filter=lambda automation_parameters, sentinel_parameters: automation_parameters["persistenceMaxTimeout"] > 0
            and sentinel_parameters["sentinel_parameter"] > 10,
            severity=AlertSeverity.WARNING,
            code=1004,
            msg="Parameterized Sentinel warning (in Sentinel Warning Procedure)",
            applies_in_procedures=["Parameterized Sentinel Warning"],
            sentinel_parameters=["sentinel_parameter"],
            automation_parameters=["persistenceMaxTimeout"],  # From automation.yaml
        ),
        SentinelRule(
            filter=lambda: True,
            connections_to_check=[("B1", "V2")],
            severity=AlertSeverity.WARNING,
            code=1002,
            msg="Connection exists between B1 and V2",
            applies_in_procedures=["Sentinel Graph Warning"],
        ),
    ],
    sentinel_parameters={"sentinel_parameter": 11},
)


sentry = SentryConfig(
    [
        SentryRule(
            filter=lambda: True,
            severity=AlertSeverity.WARNING,
            code=2003,
            msg="Sentry Open Valve Procedure entered",
            applies_in_procedures=["Sentry Open Valve"],
            command=lambda: device.valve_on("V2"),
            deprecate=timedelta(minutes=1),
        ),
    ]
)
