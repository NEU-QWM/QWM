from datetime import timedelta

from core.device import device
from core.device.command import AlertSeverity
from core.sentinel.rules import SentryRule, ParameterizedSentryRule
from sm.general.helpers import Helpers


sentry_heaters_off = SentryRule(
    filter=lambda _4K_TEMPERATURE: _4K_TEMPERATURE > 306,
    severity=AlertSeverity.ERROR,
    code=1001,
    msg="4K Temperature over 306 K, turning off heaters",
    command=lambda parameters: Helpers.warmup_heater_off(parameters),
    deprecate=timedelta(minutes=1),
)

def sentry_valve_room_temperature_actions():
    device.valve_off("V111")
    device.valve_on("V110")

sentry_vent_valve_room_temperature = ParameterizedSentryRule(
    filter=lambda STILL_TEMPERATURE, P6_PRESSURE, V104_ENABLED, V101_ENABLED, automation_parameters, sentinel_parameters: float(STILL_TEMPERATURE)> automation_parameters["systemWarmTemperature"] and float(P6_PRESSURE) > 1.15 and V104_ENABLED and V101_ENABLED,
    severity=AlertSeverity.ERROR,
    code=1002,
    msg="P6 over 1.15 bar, venting through V110",
    # → open V110 (Vent valve)
    command= sentry_valve_room_temperature_actions,
    deprecate=timedelta(minutes=1),
    automation_parameters=["systemWarmTemperature"],
)


def sentry_valve_low_temperature_actions():
    device.valves_off(["V101","V102","V104","V105","V106","V107",
                       "V108","V109","V110","V111","V112", "V113",
                       "V114","V303","V306","V404","V406"])

sentry_vent_valve_low_temperature = ParameterizedSentryRule(
    filter=lambda STILL_TEMPERATURE, P6_PRESSURE, V104_ENABLED, V101_ENABLED, automation_parameters, sentinel_parameters: float(STILL_TEMPERATURE)< automation_parameters["systemWarmTemperature"] and float(P6_PRESSURE) > 1.15 and V104_ENABLED and V101_ENABLED,
    severity=AlertSeverity.ERROR,
    code=1003,
    msg="P6 over 1.15 bar, close service manifold valves",
    # → open V110 (Vent valve)
    command= sentry_valve_low_temperature_actions,
    deprecate=timedelta(minutes=1),
    automation_parameters=["systemWarmTemperature"],
)









## Unittest ##

# the sentry below is for unittest purposes
sentry_vent_valve_unittest = SentryRule(
    filter=lambda P6_PRESSURE, V104_ENABLED, V101_ENABLED: P6_PRESSURE > 1.15 and V104_ENABLED and V101_ENABLED,
    severity=AlertSeverity.ERROR,
    code=1002,
    msg="P6 over 1.15 bar, venting through V110",
    # → open V110 (Vent valve)
    command=lambda: device.valve_on("V110"),
    deprecate=timedelta(minutes=1),
)





