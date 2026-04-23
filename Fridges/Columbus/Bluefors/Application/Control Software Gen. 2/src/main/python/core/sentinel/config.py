from dataclasses import dataclass, field


from .rules import SentinelRule, SentryRule
from . import Sentinel


@dataclass
class SentinelConfig:
    rules: list[SentinelRule]
    sentinel_parameters: dict = field(default_factory=dict)
    automation_parameters: dict = field(default_factory=dict)

    def sentinel(self, graph=None):
        return Sentinel(self, graph)

@dataclass
class SentryConfig:
    rules: list[SentryRule]
    sentinel_parameters: dict = field(default_factory=dict)
    automation_parameters: dict = field(default_factory=dict)

    def sentry(self, graph=None):
        return Sentinel(self, graph)
