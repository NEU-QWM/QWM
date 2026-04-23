from typing import Optional

from config import AutomationConfig
from core import utils
from core.device.command import Alert
from core.sentinel import Sentinel


class SentinelHandler:
    def __init__(self, sentinel_config=None, sentry_config=None):
        if sentinel_config:
            self.sentinel: Optional[Sentinel] = Sentinel(sentinel_config)
        if sentry_config:
            self.sentry: Optional[Sentinel] = Sentinel(sentry_config)
        self.active_sentry_alerts = dict()
        self.automation_parameters = dict()

    def start(self, config: AutomationConfig):
        self.sentinel = Sentinel(config.sentinel, config.device_graph)
        self.sentry = Sentinel(config.sentry, config.device_graph)
        # Parameters from automation.yaml, like numberOf4KHeaters -- sometimes
        # needed in Sentry actions
        self.automation_parameters = config.parameters

    def stop(self):
        self.sentinel = None
        self.sentry = None

    def is_deprecated(self, alert):
        return (alert.deprecate is not None) and (alert.deprecate <= (utils.tznow() - self.active_sentry_alerts[alert]))

    def check_with_sentinel(self, new_state: dict, change: dict) -> list[Alert]:
        """
        Sentinel only -- before device commands, "speculate".
        """
        if not self.sentinel:
            # TODO: We could raise here
            return []
        else:
            old_alerts = {alert for alert in self.sentinel.check_new_state(new_state)}
            new_alerts = {alert for alert in self.sentinel.check_new_state(new_state | change)}
            return [alert.format() for alert in (new_alerts - old_alerts)]

    def check(self, new_state: dict):
        if not self.sentinel:
            return []

        alerts = self.sentinel.check_new_state(new_state)
        sentry_alerts = self.sentry.check_new_state(new_state) if self.sentry is not None else []

        return [alert.format() for alert in alerts] + self.handle_sentry_alerts(sentry_alerts)

    def handle_sentry_alerts(self, alerts):
        formatted_alerts = []
        now = utils.tznow()
        # 1. Remove inactive alerts
        for alert in list(self.active_sentry_alerts):
            if alert not in alerts:
                self.active_sentry_alerts.pop(alert)

        for alert in alerts:
            # 2. If we see a new alert or an old one timeouts, run action and
            # update the 'last activation time'
            if alert not in self.active_sentry_alerts or self.is_deprecated(alert):
                alert.execute(self.automation_parameters)
                self.active_sentry_alerts[alert] = now
                formatted_alerts.append(alert.format(now.isoformat()))
            else:
                formatted_alerts.append(alert.format(self.active_sentry_alerts[alert].isoformat()))
        return formatted_alerts
