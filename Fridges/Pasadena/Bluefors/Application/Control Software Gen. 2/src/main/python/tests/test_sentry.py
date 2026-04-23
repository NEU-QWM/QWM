import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import core.api
import sm.manual.statemachine
import tests.api
from config import AutomationConfig
from configuration.hardware import SystemType
from core.device import device
from core.device.command import SentinelAlert, SentryAlert
from core.handlers.sentinel import SentinelHandler
from core.sentinel.config import SentinelConfig, SentryConfig
from core.sentinel.rules import AlertSeverity, SentryRule
from sm.general.sentry_rules import sentry_heaters_off, sentry_vent_valve_unittest

patch.TEST_PREFIX = (
    "test",
    "setUp",
)


pressure_too_high_open_valve = SentryRule(
    filter=lambda PRESSURE: PRESSURE > 10,
    severity=AlertSeverity.ERROR,
    code=1234,
    msg="Pressure too high: {PRESSURE}",
    command=lambda: device.valve_on("V001"),
)


class MySentryRule(SentryRule):
    def action(self, parameters):
        device.valve_on("V002")
        device.valve_on("V003")


pressure_too_high_run_several_commands = MySentryRule(
    filter=lambda PRESSURE: PRESSURE > 10, severity=AlertSeverity.ERROR, code=1234, msg="Pressure too high: {PRESSURE}"
)


@patch("core.api", new=tests.api.TestApi())
class TestSentry(unittest.TestCase):
    def setUp(self):
        self.state = core.api.state
        self.sentry = SentryConfig([pressure_too_high_open_valve, pressure_too_high_run_several_commands]).sentry()

    def tearDown(self):
        pass

    def test_sentry(self):
        """
        Sentry returns correct alerts
        """
        no_alerts = self.sentry.check_new_state({"PRESSURE": 9})
        self.assertFalse(no_alerts)  # Check that no_alerts is empty

        alerts = self.sentry.check_new_state({"PRESSURE": 11})
        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertEqual(alerts[0].execute, pressure_too_high_open_valve.execute)
        self.assertEqual(alerts[1].execute, pressure_too_high_run_several_commands.execute)


@patch("core.api", new=tests.api.TestApi())
class TestSentryHandler(unittest.TestCase):
    def setUp(self):
        self.handler = SentinelHandler(
            SentinelConfig([]),
            SentryConfig([pressure_too_high_open_valve, pressure_too_high_run_several_commands]),
        )
        self.devices = core.api.devices

    def tearDown(self):
        self.devices.clear()

    @patch("core.utils.tznow", return_value=datetime(2000, 1, 1))
    def test_sentry_handler(self, mock_time):
        """
        Only the corresponding rules are checked for check (both Sentry and
        Sentinel) and check_with_sentinel methods
        """
        # No alerts from either when rules are not triggered
        sentinel_and_sentry_alerts = self.handler.check({"PRESSURE": 9})
        sentinel_alerts = self.handler.check({"PRESSURE": 9})
        self.assertEqual(sentinel_and_sentry_alerts, [])
        self.assertEqual(sentinel_alerts, [])

        # No Sentinel rules: no alerts
        sentinel_alerts = self.handler.check_with_sentinel({"PRESSURE": 11}, {})
        self.assertEqual(sentinel_alerts, [])

        # Sentry rules triggered
        sentinel_and_sentry_alerts = self.handler.check({"PRESSURE": 11})
        self.assertEqual(len(sentinel_and_sentry_alerts), 2)
        self.assertEqual(
            sentinel_and_sentry_alerts[0],
            SentryAlert.from_rule(pressure_too_high_open_valve, {"PRESSURE": 11}).format(mock_time().isoformat()),
        )
        self.assertEqual(
            sentinel_and_sentry_alerts[1],
            SentryAlert.from_rule(pressure_too_high_run_several_commands, {"PRESSURE": 11}).format(
                mock_time().isoformat()
            ),
        )

    def test_sentry_handler_actions(self):
        """
        Sentry correctly issues the actions defined for the rules
        """
        self.assertEqual(self.devices, {})
        self.handler.check({"PRESSURE": 11})
        self.assertEqual(
            self.devices,
            {
                "V001": {"device_on": True},
                "V002": {"device_on": True},
                "V003": {"device_on": True},
            },
        )


@patch("core.api", new=tests.api.TestApi())
class TestSentryHandlerState(unittest.TestCase):
    @staticmethod
    def get_rule_with_deprecation(deprecate):
        return SentryRule(
            filter=lambda PRESSURE: PRESSURE > 10,
            severity=AlertSeverity.ERROR,
            code=1234,
            msg="Pressure too high: {PRESSURE}",
            command=lambda: device.valve_on("V001"),
            deprecate=deprecate,  # Deprecated immediately
        )

    def setUp(self):
        self.device_command = core.api.device_command = MagicMock()
        self.handler = SentinelHandler()

    def tearDown(self):
        self.handler.stop()

    def test_sentry_do_not_use_msg_for_identity(self):
        self.handler = SentinelHandler(
            SentinelConfig([]),
            SentryConfig([pressure_too_high_open_valve]),
        )
        self.handler.check({"PRESSURE": 11.1})
        self.handler.check({"PRESSURE": 11.2})
        self.device_command.assert_called_once()

    def test_sentry_do_not_trigger_actions_twice(self):
        self.handler = SentinelHandler(
            SentinelConfig([]),
            SentryConfig([pressure_too_high_open_valve]),
        )
        self.handler.check({"PRESSURE": 11})
        self.handler.check({"PRESSURE": 11})
        self.device_command.assert_called_once()

    def test_sentry_trigger_again_after_deprecated_default(self):
        DEPRECATE = timedelta(0)
        self.handler = SentinelHandler(
            SentinelConfig([]),
            SentryConfig([self.get_rule_with_deprecation(DEPRECATE)]),
        )
        self.assertEqual(self.device_command.call_count, 0)
        self.handler.check({"PRESSURE": 11})
        self.assertEqual(self.device_command.call_count, 1)
        self.handler.check({"PRESSURE": 11})
        self.assertEqual(self.device_command.call_count, 2)

    def test_sentry_trigger_again_never(self):
        DEPRECATE = None
        self.handler = SentinelHandler(
            SentinelConfig([]),
            SentryConfig([self.get_rule_with_deprecation(DEPRECATE)]),
        )
        self.assertEqual(self.device_command.call_count, 0)
        self.handler.check({"PRESSURE": 11})
        self.assertEqual(self.device_command.call_count, 1)

        # Not triggered again:
        self.handler.check({"PRESSURE": 11})
        self.assertEqual(self.device_command.call_count, 1)

        # Not triggered for a call when alert is not raised:
        self.handler.check({"PRESSURE": 9})
        self.assertEqual(self.device_command.call_count, 1)

        # Triggered again after not being seen for a call:
        self.handler.check({"PRESSURE": 11})
        self.assertEqual(self.device_command.call_count, 2)

    @patch("core.utils.tznow", return_value=datetime(2000, 1, 1))
    def test_sentry_trigger_not_triggered_early(self, mock_time):
        DEPRECATE = timedelta(hours=1)
        self.handler = SentinelHandler(
            SentinelConfig([]),
            SentryConfig([self.get_rule_with_deprecation(DEPRECATE)]),
        )
        self.assertEqual(self.device_command.call_count, 0)
        alerts = self.handler.check({"PRESSURE": 11})
        self.assertEqual(self.device_command.call_count, 1)

        # Not triggered again after 59 minutes:
        mock_time.return_value = datetime(2000, 1, 1, minute=59)
        self.assertEqual(self.handler.check({"PRESSURE": 11}), alerts)
        self.assertEqual(self.device_command.call_count, 1)

        # Triggered after 1 hour has passed:
        mock_time.return_value = datetime(2000, 1, 1, hour=1)
        new_alerts = self.handler.check({"PRESSURE": 11})
        self.assertNotEqual(new_alerts, alerts)
        # Only difference is the activation_id:
        alerts[0].pop("activation_id")
        new_alerts[0].pop("activation_id")
        self.assertEqual(new_alerts, alerts)
        self.assertEqual(self.device_command.call_count, 2)


@patch("core.api", new=tests.api.TestApi())
class TestSentryRules(unittest.TestCase):
    def setUp(self):
        automation_config = AutomationConfig(
            "test", sm.manual.statemachine, SystemType.PYTHON_TEST, {"numberOf4KHeaters": 3}
        )
        automation_config.sentry = SentryConfig([sentry_heaters_off, sentry_vent_valve_unittest])

        self.state = core.api.state
        self.valid_state = {"4K_TEMPERATURE": 306, "P6_PRESSURE": 1.3, "V104_ENABLED": False, "V101_ENABLED": False}
        self.handler = SentinelHandler()
        self.handler.start(automation_config)

    def tearDown(self):
        pass

    def test_sentry(self):
        """
        Sentry returns correct alerts
        """
        no_alerts = self.handler.check(self.valid_state)
        self.assertFalse(no_alerts)  # Check that no_alerts is empty

        alerts = self.handler.check(self.valid_state | {"4K_TEMPERATURE": 307})
        self.assertTrue(alerts)  # Check that alerts is nonempty

        alerts = self.handler.check(self.valid_state | {"P6_PRESSURE": 1.3, "V104_ENABLED": True, "V101_ENABLED": True})
        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertDictEqual(
            core.api.devices,
            {
                "4K_HEATER_1_ENABLED": {"device_on": False},
                "4K_HEATER_2_ENABLED": {"device_on": False},
                "4K_HEATER_3_ENABLED": {"device_on": False},
                "V110": {"device_on": True},
            },
        )
