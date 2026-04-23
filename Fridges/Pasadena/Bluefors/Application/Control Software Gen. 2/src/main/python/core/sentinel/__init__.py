from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from core.sentinel.graph import DeviceGraph, connected
from py_rete import ReteNetwork
from py_rete.common import WME

if TYPE_CHECKING:
    from core.sentinel.config import SentinelConfig, SentryConfig

logger = logging.getLogger(__name__)


class Sentinel:
    def __init__(self, config: SentinelConfig | SentryConfig, graph: Optional[DeviceGraph] = None):
        self.rules = config.rules
        self.variables = {v for rule in self.rules for v in rule.variables}
        self.variables.discard("existing_connections")

        # Graph-based rules
        self.graph = graph
        self.connections_to_check = {c for rule in self.rules for c in rule.connections_to_check}
        if self.connections_to_check and self.graph is None:
            raise Exception("No graph defined for Sentinel but rules contain connections!")

        # Workaround for 4K_TEMPERATURE: Add leading underscore to be able to use it as variable
        # name. Use _4K_TEMPERATURE from _variables internally, 4K_TEMPERATURE when fetching values.
        self.mappings = {v: v.lstrip("_") for v in self.variables}

        self.sentinel_parameters = config.sentinel_parameters
        self.automation_parameters = config.automation_parameters

        ## Evaluate SentinelAlertRules into py_rete Productions
        for rule in self.rules:
            # evaluated here to raise errors early in case of missing parameters
            rule.to_production(self.sentinel_parameters, self.automation_parameters)

        self.running = True
        logger.debug("Sentinel initialized")

    def add_wme(self, net, key, value):
        wme = WME("State", key, value)
        net.add_wme(wme)

    def get_sentinel_state(self, new_state):
        """
        Picks the needed variables from new_state and resolves mappings to
        correct variables names, if necessary.
        """
        state = {key: new_state[key] for key in self.mappings.values() if key in new_state}

        if self.graph is not None:
            connections = []
            for connection in self.connections_to_check:

                if connected(self.graph, *connection, new_state):
                    connections.append(connection)

            state["existing_connections"] = tuple(connections)

        # Handle variables starting with numbers, maps e.g. 4K_TEMPERATURE to
        # _4K_TEMPERATURE
        for key, val in self.mappings.items():
            if val in state:
                state[key] = state[val]

        return state

    def check_new_state(self, new_state: dict):
        """
        Ask sentinel whether `new_state` is a valid state and does not trigger
        sentinel rules. Returns list of raised alerts if some were triggered.

        #XXX: By creating and generating a new ReteNetwork for each request, we
        lose the working memory benefits from the Rete algorithm to not
        evaluate unchanged nodes again.

        It was done to get around handling multiple requests coming in at once,
        which might modify the rete network concurrently. Other solution would
        be to only have a single ReteNetwork, and to use locks to allow only a
        single request to access and modify it at once.

        That solution should be explored once the rete networks grow big enough
        that there will be benefits from the memory in the rete network.

        It is possible that simply adding locks on Python side is not enough,
        and the concurrency needs proper handling on Java side too, to avoid
        deadlocks. Alternatively, using a thread-safe copy of the rete network
        could be used, with a 'master' that is updated intermittently.
        """
        try:
            state = self.get_sentinel_state(new_state)

            # Evaluate SentinelAlertRules into py_rete Productions
            net = ReteNetwork()
            for rule in self.rules:
                production = rule.to_production(self.sentinel_parameters, self.automation_parameters)
                net.add_production(production)

            for key, value in state.items():
                try:
                    self.add_wme(net, key, value)
                except TypeError:
                    logger.info(f"Error adding value for a Sentinel rule: unhashable value {value}")

            # Rete network returns two alerts for top-level OR'd conditions, e.g.
            # OR(A, B) gives two alerts if A and B are both true.
            # Keep only unique alerts, using dict instead of set preserves order
            alerts = list(dict.fromkeys(self.fire(net)))
            return alerts

        except Exception as e:
            logger.error("Unexpected error", exc_info=True)
            raise e

    @staticmethod
    def fire(net):
        try:
            matches = list(net.matches)
            return [match.fire() for match in matches]
        except Exception as e:
            logger.error("Failed to evaluate the RETE network", e)
            return []
