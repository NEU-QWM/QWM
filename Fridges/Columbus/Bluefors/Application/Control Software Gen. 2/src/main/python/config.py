from dataclasses import dataclass

from configuration.hardware import SystemType, sentinel_parameters
from core.sentinel.config import SentinelConfig, SentryConfig
from core.sentinel.graph import DeviceGraph
from core.state_machine.config import StateMachineConfig


@dataclass
class AutomationConfig:
    automation_name = None
    system_type: SystemType
    statemachine: StateMachineConfig
    sentinel: SentinelConfig
    sentry = SentryConfig
    parameters: dict
    device_graph: None | DeviceGraph
    ready = False

    def __init__(self, name, config_module, system_type, parameters, device_graph=None):
        self.automation_name = name
        self.system_type = system_type
        self.statemachine = config_module.config
        self.sentinel = config_module.sentinel
        self.sentry = config_module.sentry
        self.parameters = parameters
        self.device_graph = device_graph
        self.ready = True

        # hardware specific overrides for Sentinel parameters that don't come from automation.yaml
        self.sentinel.sentinel_parameters |= sentinel_parameters[system_type]

        # automation.yaml parameters
        self.sentinel.automation_parameters = parameters
        self.sentry.automation_parameters = parameters
