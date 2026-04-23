from core.device.command import AlertSeverity
from core.sentinel.rules import SentinelRule

temp_b1_above_100 = SentinelRule(
        filter=lambda B1_TEMPERATURE: B1_TEMPERATURE > 323,
        severity=AlertSeverity.WARNING,
        code=1201,
        msg='Temperature of pump B1 above 323 K: {B1_TEMPERATURE}'
)

pressure_for_b1_too_high = SentinelRule(
        filter=lambda P2_PRESSURE, B1_ENABLED: P2_PRESSURE > 0.01 and P2_PRESSURE <= 0.02 and B1_ENABLED,
        severity=AlertSeverity.WARNING,
        code=1202,
        msg='Pressure for pump B1 too high for stable operation: {P2_PRESSURE}',
)

pressure_for_b1_too_high_error = SentinelRule(
        filter=lambda P2_PRESSURE, B1_ENABLED: P2_PRESSURE > 0.02 and B1_ENABLED,
        severity=AlertSeverity.ERROR,
        code=1203,
        msg='Pressure for pump B1 too high for stable operation: {P2_PRESSURE}',
)

flow_exceptionally_high = SentinelRule(
        filter=lambda FLOW_VALUE, B1_ENABLED: FLOW_VALUE > 1 and B1_ENABLED,  # TODO Add proper comparison for FLOW_VALUE
        severity=AlertSeverity.ERROR,
        code=1204,
        msg='Flow in system exceptionally high: {FLOW_VALUE}'
)

cooling_water_line = SentinelRule(
        filter=lambda COOLING_WATER_TEMPERATURE: COOLING_WATER_TEMPERATURE > 303,
        severity=AlertSeverity.WARNING,
        code=1205,
        msg='Cooling water line above 303 K from pump B1'
)


# An example of an alternative way to determine an expression for an alert rule
def _cooling_water_line_flow_expression(COOLING_WATER_FLOW):
    return COOLING_WATER_FLOW < 10


cooling_water_line_flow = SentinelRule(
        filter=_cooling_water_line_flow_expression,
        severity=AlertSeverity.WARNING,
        code=1206,
        msg='Cooling water line flow too low: {COOLING_WATER_FLOW}'
)
