import time
import unittest
from unittest.mock import patch, MagicMock

from core.device.command import SentinelAlert
import automation
from core.sentinel.config import SentinelConfig
from core.sentinel.rules import AlertSeverity, ParameterizedSentinelRule, SentinelRule

import core.api
import tests.api

patch.TEST_PREFIX = (
    "test",
    "setUp",
)


pressure_too_high_error = SentinelRule(
    filter=lambda PRESSURE: PRESSURE > 10, severity=AlertSeverity.ERROR, code=1234, msg="Pressure too high: {PRESSURE}"
)


pressure_too_high_error_in_certain_procedure = SentinelRule(
    filter=lambda PRESSURE: PRESSURE > 10,
    applies_in_procedures=["Manual"],
    severity=AlertSeverity.ERROR,
    code=1235,
    msg="Pressure too high: {PRESSURE} while in Manual state",
)


@patch("core.api", new=tests.api.TestApi())
class TestSentinel(unittest.TestCase):
    def setUp(self):
        self.state = core.api.state
        self.sentinel = SentinelConfig(
            [pressure_too_high_error, pressure_too_high_error_in_certain_procedure]
        ).sentinel()
        self.valid_state = {"PRESSURE": 9, "current_procedure": "Not Manual"}

    def tearDown(self):
        pass

    def test_sentinel(self):
        self.state.clear()
        alerts = self.sentinel.check_new_state(self.valid_state)
        self.assertFalse(alerts)  # Check that alerts is empty

        alerts = self.sentinel.check_new_state(self.valid_state | {"PRESSURE": 11})
        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert, SentinelAlert(severity=AlertSeverity.ERROR, code=1234, text="Pressure too high: 11"))

        alerts = self.sentinel.check_new_state(self.valid_state | {"PRESSURE": 11, "current_operation": "Manual", "current_procedure": "Manual"})
        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertEqual(len(alerts), 2)
        alert1, alert2 = alerts[0], alerts[1]
        self.assertEqual(alert1, SentinelAlert(severity=AlertSeverity.ERROR, code=1234, text="Pressure too high: 11"))
        self.assertEqual(
            alert2,
            SentinelAlert(severity=AlertSeverity.ERROR, code=1235, text="Pressure too high: 11 while in Manual state"),
        )

    def test_sentinel_state_filtering(self):
        alerts = self.sentinel.check_new_state(self.valid_state | {"DICT_VALUE": {"key": "value"}, "LIST_VALUE": [1, 2]})
        self.assertFalse(alerts)  # Check that alerts is empty
        alerts = self.sentinel.check_new_state(self.valid_state | {"PRESSURE": 11, "DICT_VALUE": {"key": "value"}, "LIST_VALUE": [1, 2]})
        self.assertTrue(alerts)  # Check that alerts is nonempty

    def test_sentinel_missing_values(self):
        """
        Nothing logged at least on INFO level in case of missing variables,
        since it is an expected scenario.

        Rules are not filtered against missing or disabled devices, but they
        only trigger alerts if all variables are present.
        """
        with self.assertNoLogs(level="INFO"):
            self.sentinel.check_new_state({})


@patch("core.api", new=tests.api.TestApi())
class TestSentinelPartTwo(unittest.TestCase):
    def tearDown(self):
        pass

    def test_should_trigger_milestone_a_sentinel_rules(self):
        state = core.api.state
        state.clear()
        state["roughPumpingMaxTime"] = 200
        state["boosterPumpingMaxTime"] = 500
        state["boosterStartPressureLimit"] = 1.2
        state["boosterBasePressureLimit"] = 1
        state["zeroCirculationFlowLimit"] = 10
        state["coolingWaterLimitToStartPumping"] = 26
        state["initialValueWaitTime"] = 10
        core.api.set_value("P2_PRESSURE", 900)
        core.api.set_value("FLOW_VALUE", 0.5)
        core.api.set_value("B1_ENABLED", False)
        core.api.set_value("B1_TEMPERATURE", 320)
        core.api.set_value("STILL_HEATING_POWER", 0)
        core.api.set_value("STILL_HEATER_ENABLED", False)
        core.api.set_value("COOLING_WATER_FLOW", 11)

        automation.start_automation("milestone-a")
        time.sleep(0.01)
        alerts = automation.check_with_sentinel_and_sentry(
            state.data | {
                "B1_ENABLED": True,
                "COOLING_WATER_TEMPERATURE": 350,
                "P2_PRESSURE": 1100,
                "current_operation": core.api.get("currentOperation").get("name"),
                "current_procedure": core.api.get("currentOperation").get("currentProcedure")
            }
        )
        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertEqual(len(alerts), 2)
        alert1, alert2 = alerts
        self.assertEqual(alert1["code"], 1203)
        self.assertEqual(alert2["code"], 1205)

    def test_state_rete_network_should_stay_the_same_in_case_of_error_level_alerts(self):
        state = core.api.state
        automation.start_automation("sentinel-test")

        core.api.set_value("V2_ENABLED", False)

        time.sleep(0.01)
        alerts = automation.check_with_sentinel_and_sentry(
            state.data | {
                "V2_ENABLED": True,
            }
        )

        # Check that alerts are correct
        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["code"], 1234)

        # Make sure this also works when no alerts are raised
        alerts = automation.check_with_sentinel_and_sentry(
            state.data | {
                "V2_ENABLED": False,
            }
        )
        self.assertFalse(alerts)


@patch("core.api", new=tests.api.TestApi())
class TestParameterizedSentinel(unittest.TestCase):
    parameterized_pressure_too_high_error = ParameterizedSentinelRule(
        filter=lambda VARIABLE2, PRESSURE, sentinel_parameters, automation_parameters: PRESSURE
        > sentinel_parameters["pressure_limit"],
        severity=AlertSeverity.ERROR,
        code=1234,
        msg="Pressure too high: {PRESSURE}",
        sentinel_parameters=["pressure_limit"],
    )

    parameterized_pressure_too_high_error2 = ParameterizedSentinelRule(
        filter=lambda PRESSURE, VARIABLE2, automation_parameters, sentinel_parameters: PRESSURE
        > sentinel_parameters["pressure_limit"],
        severity=AlertSeverity.ERROR,
        code=1235,
        msg="Pressure too high: {PRESSURE}",
        sentinel_parameters=["pressure_limit"],
    )

    def setUp(self):
        self.state = core.api.state
        self.state.clear()
        self.sentinel = SentinelConfig(
            [
                self.parameterized_pressure_too_high_error,
                self.parameterized_pressure_too_high_error2,
            ],
            sentinel_parameters={"pressure_limit": 10, "unused_parameter": False},
        ).sentinel()

    def test_sentinel(self):
        alerts = self.sentinel.check_new_state({"PRESSURE": 9, "VARIABLE2": 0})
        self.assertFalse(alerts)  # Check that alerts is empty

        alerts = self.sentinel.check_new_state({"PRESSURE": 11, "VARIABLE2": 0})
        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertEqual(len(alerts), 2)
        alert = alerts[0]
        self.assertEqual(alert, SentinelAlert(severity=AlertSeverity.ERROR, code=1234, text="Pressure too high: 11"))

    def test_missing_parameter_raises(self):
        with self.assertRaisesRegex(Exception, "Not all parameters available for a Sentinel rule"):
            SentinelConfig(
                [
                    self.parameterized_pressure_too_high_error,
                ],
                sentinel_parameters={"unused_parameter1": 10, "unused_parameter2": False},
            ).sentinel()

    def test_incorrect_filter_arguments_raises(self):
        with self.assertRaisesRegex(Exception, "ParameterizedRule filter function missing sentinel_parameters"):
            ParameterizedSentinelRule(
                filter=lambda PRESSURE, VARIABLE2, parameters: True,
                severity=AlertSeverity.ERROR,
                code=1235,
                msg="Pressure too high: {PRESSURE}",
                sentinel_parameters=["pressure_limit"],
            ).get_filter({}, {})

        with self.assertRaisesRegex(Exception, "ParameterizedRule sentinel_parameters and automation_parameters argum"):
            ParameterizedSentinelRule(
                filter=lambda sentinel_parameters, automation_parameters, PRESSURE, VARIABLE2: True,
                severity=AlertSeverity.ERROR,
                code=1235,
                msg="Pressure too high: {PRESSURE}",
                sentinel_parameters=["pressure_limit"],
            ).get_filter({"pressure_limit": 10}, {})


@patch("core.api", new=tests.api.TestApi())
class TestParameterizedSentinelWithStateMachine(unittest.TestCase):
    def test_sentinel(self):
        state = core.api.state
        state.clear()
        state.update({"heaterPowerOnTemp": 0, "heaterPowerOffTemp": 300})

        automation.start_automation("simple")
        alerts = automation.check_with_sentinel_and_sentry({"SM_SIMPLE_TEMPERATURE": 400})

        self.assertTrue(alerts)  # Check that alerts is nonempty
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(
            alert,
            {
                "severity": "WARNING",
                "code": 1101,
                "text": "Temperature over limit: 400",
                "originator": "Sentinel",
                "cs2_error_code": 1608,
                "activation_id": "",
            },
        )

        alerts = automation.check_with_sentinel_and_sentry({"SM_SIMPLE_TEMPERATURE": 199})
        self.assertFalse(alerts)  # Check that alerts empty


@patch("core.api", new=tests.api.TestApi())
class TestSentinelGraph(unittest.TestCase):
    def setUp(self):
        self.state = core.api.state
        rule = SentinelRule(
            filter=lambda PRESSURE: PRESSURE > 10,
            connections_to_check=[('V1', 'V2')],
            severity=AlertSeverity.ERROR,
            code=1234,
            msg="Pressure too high: {PRESSURE}"
        )
        self.sentinel = SentinelConfig([rule]).sentinel(graph=MagicMock())

    def tearDown(self):
        pass

    @patch("core.sentinel.connected", new_callable=MagicMock)
    def test_sentinel(self, connected):
        self.state.clear()

        # Pressure condition not satisfied => no alerts
        connected.return_value = False
        alerts = self.sentinel.check_new_state({"PRESSURE": 9})
        self.assertFalse(alerts)  # Check that alerts is empty

        # Pressure condition satisfied, connected = True => alert
        connected.return_value = True
        alerts = self.sentinel.check_new_state({"PRESSURE": 11})
        self.assertTrue(alerts)  # Check that alerts is nonempty

        # Assert that connected is re-evaluated when pressure stays the same
        connected.return_value = False
        alerts = self.sentinel.check_new_state({"PRESSURE": 1})
        self.assertFalse(alerts)  # Check that alerts is empty
