import unittest
from unittest.mock import patch

import automation
from core.sentinel.config import SentinelConfig, SentryConfig
from core.state_machine.config import StateMachineConfig
import tests.api
from core.state_machine import router

patch.TEST_PREFIX = (
    "test",
    "setUp",
)

test_api = tests.api.TestApi()


class ConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.configs = automation.config_modules

    def tearDown(self):
        pass

    def test_automations_fully_defined(self):
        for config in automation.config_modules.values():
            self.assertTrue(hasattr(config, "config"), "Missing Statemachine config")
            self.assertEqual(type(config.config), StateMachineConfig, "Invalid type for StateMachineConfig")
            self.assertTrue(hasattr(config, "sentinel"), "Missing Sentinel config")
            self.assertEqual(type(config.sentinel), SentinelConfig, f"Invalid type for SentinelConfig {config}")
            self.assertTrue(hasattr(config, "sentry"), "Missing Sentry config")
            self.assertEqual(type(config.sentry), SentryConfig, f"Invalid type for SentryConfig {config}")
