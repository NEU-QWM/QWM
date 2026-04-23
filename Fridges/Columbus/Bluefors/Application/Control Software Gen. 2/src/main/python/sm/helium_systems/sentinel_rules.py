from core.device.command import AlertSeverity
from core.sentinel.rules import SentinelRule

pressure_difference_too_high_ln2trap = SentinelRule(
    filter=lambda P3_PRESSURE, P4_PRESSURE, current_procedure: current_procedure == 'System in circulation mode' and abs(
        float(P4_PRESSURE) - float(P3_PRESSURE)) > 0.1,
    severity=AlertSeverity.WARNING,
    code=1201,
    msg='Pressure difference over LN2 trap is large, please refer to System user manual how to clean it',
)

pressure_p3_high = SentinelRule(
    filter=lambda P3_PRESSURE, current_procedure: current_procedure == 'System in circulation mode' and float(P3_PRESSURE) > 1,
    severity=AlertSeverity.WARNING,
    code=1202,
    msg='Condensing pressure high',
)

pressure_p4_high = SentinelRule(
    filter=lambda P4_PRESSURE, current_procedure: current_procedure == 'System in circulation mode' and float(P4_PRESSURE) > 1,
    severity=AlertSeverity.WARNING,
    code=1203,
    msg='P4 pressure high',
)

