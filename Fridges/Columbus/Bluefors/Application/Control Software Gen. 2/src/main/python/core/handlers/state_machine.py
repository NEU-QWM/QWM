import logging
import time
from typing import Optional

import core.api
from config import AutomationConfig
from core import utils
from core.state_machine.exceptions import OperationFailedToStart, OperationNotFound, StateMachineNotRunning
from core.state_machine.state_machine import StateMachine

logger = logging.getLogger(__name__)


class StateMachineHandler:
    def __init__(self, statemachine: Optional[StateMachine]):
        self._statemachine = statemachine

    @property
    def statemachine(self) -> StateMachine:
        if not self._statemachine:
            raise StateMachineNotRunning()
        else:
            return self._statemachine

    def start(self, config: AutomationConfig, start=True):
        # XXX: workaround for a bug on the Java side, where HTTP API still sees
        # core state as STARTING for the first calls
        i = 0.1
        while not core.api.available():
            time.sleep(i := i * 2)
            if i > 5:
                raise Exception("Timed out while waiting for HTTP API to become available")
        core.api.set_name(config.automation_name)
        core.api.configured_devices()
        self._statemachine = StateMachine(config.statemachine, start=start)
        core.api.statemachine_started()
        logger.info(f"Statemachine {config.automation_name} started")

    def stop(self, skip_if_not_running):
        logger.debug("Called stop")
        try:
            self.statemachine.stop()
            self._statemachine = None
        except StateMachineNotRunning as e:
            if skip_if_not_running:
                pass
            else:
                raise e

    def start_operation(self, operation_name_or_id, parameters=None, include_validations=False):
        operation = self.statemachine.get_operation(operation_name_or_id, parameters, validate=False)
        if operation is None:
            logger.info(f"Failed to start automation operation {operation_name_or_id}, operation not found")
            raise OperationNotFound(
                f"Invalid operation {operation_name_or_id}, available operations are"
                f" {[op.static_name for op in self.statemachine.get_operations()]}"
            )
        if operation.static_name != "Fallback" and not operation.validate():
            logger.info(
                f"Automation operation {operation.static_name} (id: {operation.id}, parameters: {parameters}) failed to start due to validation failure"
            )
            if include_validations:
                return utils.serialize(operation.serialize())
            else:
                raise OperationFailedToStart()
        else:
            self.statemachine.stop()
            logger.info(f"Starting automation operation {operation.static_name}")
            if operation.static_name == "Fallback":
                running_operation = self.statemachine.fallback()
            else:
                running_operation = self.statemachine.run_operation(operation, parameters, threaded=True)
            logger.info(f"Automation operation {operation.static_name} started, ({running_operation.serialize()})")
        return utils.serialize(running_operation.serialize())

    def get_operations(self, include_validations):
        if include_validations:
            # Don't filter operations by validation status, return all with
            # validation info
            operations = self.statemachine.get_operations(validate=False)
            state = core.api.CachingState()
            return utils.serialize([operation.serialize(True, state) for operation in operations])
        else:
            operations = self.statemachine.get_operations(validate=True)
            return utils.serialize([operation.serialize(False) for operation in operations])

    def get_operation(self, name_or_id):
        if operation := self.statemachine.get_operation(name_or_id):
            return utils.serialize(operation.serialize())
        else:
            # XXX
            return {}
            raise OperationNotFound(f"Invalid operation {name_or_id}.")

    def get_operation_parameters(self, name_or_id):
        if operation := self.statemachine.get_operation(name_or_id):
            return utils.serialize(operation._bound_parameters)
        else:
            raise OperationNotFound(f"Invalid operation {name_or_id}.")

    def get_running_operation(self):
        if self.statemachine.current_operation:
            core.api.persist_operation(self.statemachine.current_operation)
            return utils.serialize(self.statemachine.current_operation.serialize())
        else:
            return {}

    def get_procedure_graph(self):
        return {
            "nodes": [p.as_map() for p in self.statemachine.get_procedures()],
            "edges": [(l.as_map(), r.as_map()) for l, r in self.statemachine.get_transitions()],
        }
