from core.device.command import AlertSeverity
from core.sentinel.rules import SentinelRule, ParameterizedSentinelRule

temperature_4K_too_high = SentinelRule(
    filter=lambda _4K_TEMPERATURE, current_procedure: current_procedure == "System in circulation mode"
    and float(_4K_TEMPERATURE) > 4.2,
    severity=AlertSeverity.WARNING,
    code=1104,
    msg="4K flange temperature high for stable operation",
)

temperature_50K_too_high = SentinelRule(
    filter=lambda _50K_TEMPERATURE, current_procedure: current_procedure == "System in circulation mode"
    and float(_50K_TEMPERATURE) > 60,
    severity=AlertSeverity.WARNING,
    code=1105,
    msg="50K flange temperature high for stable operation",
)

PulseTube_above_1mbar = SentinelRule(
    filter=lambda PULSE_TUBE_ENABLED, P1_PRESSURE: PULSE_TUBE_ENABLED and P1_PRESSURE > 0.001,
    severity=AlertSeverity.ERROR,
    code=1011,
    msg="Cannot turn on the pulse tube if P1 > 1mbar",
)

pressure_vacuum_can_too_high = SentinelRule(
    filter=lambda P1_PRESSURE: float(P1_PRESSURE) > 1e-7,
    applies_in_procedures=["System in circulation mode", "4K state"],
    severity=AlertSeverity.WARNING,
    code=1106,
    msg="Vacuum can pressure high",
)

gate_valve_not_open = ParameterizedSentinelRule(
    filter=lambda MXC_TEMPERATURE, V201G_ENABLED, P5_PRESSURE, automation_parameters, sentinel_parameters:
    float(P5_PRESSURE) < (automation_parameters["initialTankPressure"]-0.15) and MXC_TEMPERATURE < 2.5 and not V201G_ENABLED,
    severity=AlertSeverity.WARNING,
    code=1107,
    msg="Gate valve has to be open when helium is condensed",
    automation_parameters=["initialTankPressure"]
)

running_on_ups_power = SentinelRule(
    filter=lambda UPS_ENABLED: UPS_ENABLED,
    severity=AlertSeverity.WARNING,
    code=1108,
    msg="Power outage detected, system running on reserve power",
)

plc_in_use_locally = SentinelRule(
    filter=lambda PLC_LOCAL_ENABLED: PLC_LOCAL_ENABLED,
    severity=AlertSeverity.ERROR,
    code=1109,
    msg="GHS local control active, automation disabled",
)

# MAGNET_X_STATE:  2:HOLDING at the target field/current
magnet_x_temperature_too_high = SentinelRule(
    filter=lambda MAGNET_TEMPERATURE, MAGNET_X_STATE: MAGNET_TEMPERATURE > 4.5
    and MAGNET_X_STATE == 2,
    severity=AlertSeverity.WARNING,
    code=1110,
    msg="Magnet temperature high for stable operation",
)

magnet_y_temperature_too_high = SentinelRule(
    filter=lambda MAGNET_TEMPERATURE, MAGNET_Y_STATE: MAGNET_TEMPERATURE > 4.5
    and MAGNET_Y_STATE == 2,
    severity=AlertSeverity.WARNING,
    code=1110,
    msg="Magnet temperature high for stable operation",
)

magnet_z_temperature_too_high = SentinelRule(
    filter=lambda MAGNET_TEMPERATURE, MAGNET_Z_STATE: MAGNET_TEMPERATURE > 4.5
    and MAGNET_Z_STATE == 2,
    severity=AlertSeverity.WARNING,
    code=1110,
    msg="Magnet temperature high for stable operation",
)

tank_valve_not_open = ParameterizedSentinelRule(
    filter=lambda HELIUM_TANK_VALUE, P5_PRESSURE, automation_parameters, sentinel_parameters:
    float(P5_PRESSURE) < (automation_parameters["initialTankPressure"]-0.15) and float(HELIUM_TANK_VALUE) < 75,
    severity=AlertSeverity.WARNING,
    code=1111,
    msg="Tank manual valve has to be open when helium is condensed",
    automation_parameters=["initialTankPressure"]
)

PulseTube_above_1mbar = SentinelRule(
    filter=lambda PULSE_TUBE_ENABLED, P1_PRESSURE: PULSE_TUBE_ENABLED and P1_PRESSURE > 0.001,
    severity=AlertSeverity.ERROR,
    code=1011,
    msg="Cannot turn on the pulse tube if P1 > 1mbar",
)

prevent_vent = SentinelRule(
    filter=lambda PULSE_TUBE_ENABLED, V104_ENABLED, V101_ENABLED, V110_ENABLED, V111_ENABLED:
    PULSE_TUBE_ENABLED and V104_ENABLED and V101_ENABLED and V110_ENABLED,
    severity=AlertSeverity.ERROR,
    code=1012,
    msg="Cannot vent while Pulse Tubes are ON",
)

prevent_vent_N2 = SentinelRule(
    filter=lambda PULSE_TUBE_ENABLED, V104_ENABLED, V101_ENABLED, V111_ENABLED:
    PULSE_TUBE_ENABLED and V111_ENABLED and V104_ENABLED and V101_ENABLED,
    severity=AlertSeverity.ERROR,
    code=1012,
    msg="Cannot vent while Pulse Tubes are ON",
)

general_sentinel_rules = [
    temperature_4K_too_high,
    temperature_50K_too_high,
    pressure_vacuum_can_too_high,
    gate_valve_not_open,
    running_on_ups_power,
    plc_in_use_locally,
    tank_valve_not_open,
    PulseTube_above_1mbar,
    prevent_vent,
    prevent_vent_N2,
]

magnet_rules = [
    magnet_x_temperature_too_high,
    magnet_y_temperature_too_high,
    magnet_z_temperature_too_high,
]
