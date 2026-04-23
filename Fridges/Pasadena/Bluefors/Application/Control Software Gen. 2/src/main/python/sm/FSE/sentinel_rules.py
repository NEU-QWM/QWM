from core.device.command import AlertSeverity
from core.sentinel.rules import ParameterizedSentinelRule, SentinelRule

pressure_difference_too_high_ln2trap = SentinelRule(
    filter=lambda P3_PRESSURE, P4_PRESSURE, current_procedure: current_procedure == "System in circulation mode"
    and abs(float(P4_PRESSURE) - float(P3_PRESSURE)) > 0.1,
    severity=AlertSeverity.WARNING,
    code=1201,
    msg="Pressure difference over LN2 trap is large, please refer to System user manual how to clean it",
)

pressure_p3_high = SentinelRule(
    filter=lambda P3_PRESSURE, current_procedure: current_procedure == "System in circulation mode"
    and float(P3_PRESSURE) > 1,
    severity=AlertSeverity.WARNING,
    code=1202,
    msg="Condensing pressure high",
)

pressure_p4_high = SentinelRule(
    filter=lambda P4_PRESSURE, current_procedure: current_procedure == "System in circulation mode"
    and float(P4_PRESSURE) > 1,
    severity=AlertSeverity.WARNING,
    code=1203,
    msg="P4 pressure high",
)

# unused
mixing_chamber_heater_power_too_high = SentinelRule(
    filter=lambda MXC_HEATING_POWER: MXC_HEATING_POWER > 0.01,
    applies_in_procedures=["System in circulation mode"],
    severity=AlertSeverity.ERROR,
    code=1204,
    msg="Too high mixing chamber heater power for circulation mode",
)

# unused
still_heater_power_too_high = ParameterizedSentinelRule(
    filter=lambda STILL_HEATING_POWER, sentinel_parameters, automation_parameters: STILL_HEATING_POWER > sentinel_parameters["still_heating_power_limit"],
    applies_in_procedures=["System in circulation mode"],
    severity=AlertSeverity.ERROR,
    code=1204,
    msg="Too high still heater power for circulation mode",
    # This value ‘0.1 W’ is potentially different for GHS250/400 and GHS1000.
    sentinel_parameters=["still_heating_power_limit"],
)
