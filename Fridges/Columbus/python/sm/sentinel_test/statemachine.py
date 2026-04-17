from core.device.command import AlertSeverity
from core.sentinel.config import SentinelConfig, SentryConfig
from core.sentinel.rules import SentinelRule
from sm.manual.statemachine import config


sentinel = SentinelConfig([
        SentinelRule(
                filter=lambda V2_ENABLED: V2_ENABLED,
                severity=AlertSeverity.ERROR,
                code=1234,
                msg='Test enable valve (abstract and write)'
        ),
        SentinelRule(
                filter=lambda STILL_HEATER_ENABLED: STILL_HEATER_ENABLED,
                severity=AlertSeverity.WARNING,
                code=1234,
                msg='Test enable heater (BFTC)'
        ),
        SentinelRule(
                filter=lambda STILL_HEATING_POWER: float(STILL_HEATING_POWER) > 0.4,
                severity=AlertSeverity.WARNING,
                code=1234,
                msg='Test heater power (BFTC)'
        ),
        SentinelRule(
                filter=lambda B1_ENABLED: B1_ENABLED,
                severity=AlertSeverity.ERROR,
                code=1234,
                msg='Test turbo pump on (OPC UA device)'
        ),
    ])


sentry = SentryConfig([])
