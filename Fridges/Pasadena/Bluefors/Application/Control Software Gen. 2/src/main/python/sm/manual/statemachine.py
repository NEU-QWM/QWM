from core.sentinel.config import SentinelConfig, SentryConfig
from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import Initial, Manual


config = StateMachineConfig(
    name="manual", transitions=((Initial, Manual),), parameter_mapping={}
)


sentinel = SentinelConfig([])


sentry = SentryConfig([])
