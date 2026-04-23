from __future__ import annotations

import logging
import threading
from enum import Enum
from itertools import chain
from typing import TYPE_CHECKING, Iterable, Optional
from urllib.error import URLError

import core.api
import core.state_machine.router as router
from core.state_machine.exceptions import (
    OperationParametersNotFound,
    ProcedureError,
    ProcStoppedException,
    ValidationError,
)
from core.state_machine.operation import Operation, RunningOperation
from core.state_machine.procedure import Fallback, Initial, Manual, Procedure
from core.state_machine.typing import LoopProcedures, ProcedureT, RecoveryPaths, Transitions
from core.utils import check_parameter_type

if TYPE_CHECKING:
    from core.state_machine.config import StateMachineConfig

logger = logging.getLogger(__name__)


class Errors(Enum):
    RecoveryValidationFailed = (-1, "Operation {operation_id} Validations failed when recovering")


class StateMachine:
    def __init__(self, config: StateMachineConfig, start=True):
        self.name = config.name
        self.operations = StateMachineOperations(config)
        self.interrupt_event = threading.Event()
        self.thread = None
        self.current_operation = None

        if start:
            self.start()
        else:
            self.current_operation = self.recover()
            logger.info("Starting Automation without attempting recovery")

    @property
    def stopped(self):
        return self.current_operation is None

    @property
    def current_procedure(self):
        return Initial if not self.current_operation else self.current_operation.current_procedure

    def start(self):
        if running_operation := self.recover():
            self.run_operation(running_operation, threaded=True)
        else:
            self.manual()

    def recover(self):
        """
        Sets current_operation to recovered operation if successful
        """
        operation_map = core.api.get_internal("currentOperation", False)
        if operation_map is not None:
            return self.get_recovery_operation(operation_map)

    def stop(self):
        logging.debug("Called stop inside statemachine")
        if self.thread and self.thread.is_alive():
            self.interrupt_event.set()
            self.thread.join()
        self.current_operation = None

    def manual(self, parameters={}):
        logging.debug("StateMachine: Go to manual")
        self.current_operation = RunningOperation.start(Operation.manual(), parameters)
        core.api.persist_operation(self.current_operation, log=True)

    def fallback(self, parameters={}):
        logging.debug("StateMachine: Go to fallback")
        if self.current_operation:
            core.api.persist_operation(self.current_operation)
        self.current_operation = RunningOperation.start(Operation.fallback(), parameters)
        core.api.persist_operation(self.current_operation, log=True)
        return self.current_operation

    def _run_operation(self, current_operation: RunningOperation):
        self.interrupt_event.clear()
        try:
            current_operation.run(self.interrupt_event)
        except (URLError, ValidationError, ProcedureError) as e:
            if isinstance(e, URLError):
                logger.info("Automation failed when getting or setting value, going to Manual mode")
            if isinstance(e, ValidationError):
                logger.info(
                    f"Validations failed when trying to enter procedure {self.current_procedure.name}, check alerts for details"
                )
            if isinstance(e, ProcedureError):
                logger.info(
                    f"Automation encountered an error while running procedure {self.current_procedure.name}, check alerts for details"
                )
            self.manual()
        except (ProcStoppedException, KeyboardInterrupt):
            logger.info(f"Automation operation stopped by user while in procedure {self.current_procedure.name}")
            current_operation.running = False
            core.api.persist_operation(current_operation)

    def run_operation(self, operation: Operation | RunningOperation, user_parameters={}, threaded=False):
        self.stop()

        if isinstance(operation, Operation):
            parameters = self.operations.resolve_parameters(operation.parameters, user_parameters)
            self.current_operation = RunningOperation.start(operation, parameters)
        elif isinstance(operation, RunningOperation):
            self.current_operation = operation

        if threaded:
            self.thread = threading.Thread(target=self._run_operation, args=(self.current_operation,))
            self.thread.start()
        else:
            self._run_operation(self.current_operation)
        return self.current_operation

    def get_recovery_operation(self, operations_map) -> RunningOperation | None:
        for operation in self.get_recovery_operations(operations_map):
            logger.info(f"Checking if recovery to {operation.operation.static_name} is valid")
            if procedure := operation.find_valid_start_procedure():
                operation.current_procedure = procedure
                return operation

    def get_recovery_operations(self, operation_map) -> Iterable[RunningOperation]:
        deserialized_operation: RunningOperation | None = RunningOperation.deserialize(
            operation_map, self.operations.procedures, self.operations.procedure_graph
        )
        if deserialized_operation:
            previous_operation: Operation = deserialized_operation.operation
            # 1. Try recovery along the recovered operation path
            if (
                previous_operation in self.operations.operations(previous_operation.start)
                or previous_operation in self.operations.recovery_operations()
            ):
                yield deserialized_operation

            # 3. If separate recovery paths exist, try those
            for recovery_operation in self.operations.recovery_operations():
                if previous_operation.goal == recovery_operation.goal:
                    # Give operation.parameters as user parameters to use them instead of defaults
                    parameters = self.operations.resolve_parameters(
                        recovery_operation.parameters, user_parameters=deserialized_operation.parameters
                    )
                    yield RunningOperation.start(recovery_operation, parameters)

    def get_operations(self, validate=True):
        operations = self.operations.operations(self.current_procedure)
        parameters = self.operations.resolve_parameters({parameter for op in operations for parameter in op.parameters})

        for operation in operations:
            operation.bind_parameters(parameters, self.operations.parameter_mapping)
        if validate:
            # Restrict the number of HTTP calls made when validating the
            # operations, since otherwise we would end up fetching same value
            # hundreds of times
            state = core.api.CachingState()
            operations = filter(lambda operation: operation.validate(state=state), operations)
        return list(operations)

    def get_operation(self, name_or_id: str, user_parameters=None, validate=False):
        if name_or_id == "Fallback":
            return Operation.fallback()

        operation = self.operations.get_operation(self.current_procedure, name_or_id)
        if operation:
            parameters = self.operations.resolve_parameters(operation.parameters, user_parameters)
            operation.bind_parameters(parameters, self.operations.parameter_mapping)
            if not validate or (validate and operation.validate()):
                return operation

    def get_procedures(self):
        return self.operations.procedures.difference({Initial, Fallback, Manual})

    def get_transitions(self):
        return self.operations.get_transitions()


class StateMachineOperations:
    def __init__(self, config: StateMachineConfig):
        self.procedure_graph, self.procedures = self.inject_manual_procedure(
            config.transitions, config.loop_procedures, config.recovery_paths
        )
        self.parameter_mapping = config.parameter_mapping
        self.loop_procedures = config.loop_procedures or {}
        self.recovery_paths = config.recovery_paths or []
        self.parameter_types = core.api.get_parameter_types()

        # Assert all parameters required by procedures are given
        required_parameters = {parameter for p in self.procedures for parameter in p.required_parameters}
        if missing := set(required_parameters) - self.parameter_mapping.keys():
            raise Exception(f"Missing parameters {missing}")

        try:
            self.resolve_parameters(required_parameters, check_types=False)
        except OperationParametersNotFound:
            raise Exception(
                f"Not all parameters declared in procedures were available, expected: {required_parameters}"
            )

        if not len(self.procedures) == len({procedure.name for procedure in self.procedures}):
            raise Exception("Every Procedure in the graph must have a unique name")

    @staticmethod
    def inject_manual_procedure(
        procedure_graph: Transitions,
        loop_procedures: Optional[LoopProcedures],
        recovery_paths: Optional[RecoveryPaths],
    ) -> tuple[Transitions, set[ProcedureT]]:
        """
        Adds the bidirectional transitions from Manual mode to normal
        procedures, and unidirectional transitions from 'loop procedures' and
        'alternate recovery path' procedures to Manual
        """
        # Flatten the transitions to a single set
        procedures = {procedure for transition_tuple in procedure_graph for procedure in transition_tuple}
        if loop_procedures is not None:
            procedures |= set(chain(*chain(*loop_procedures.values())))
        procedures.add(Manual)
        procedures.add(Fallback)

        # Add bidirectional transitions from any procedure to Manual
        additional_transitions = []
        for procedure in procedures:
            if procedure not in (Initial, Manual, Fallback):
                additional_transitions.append((procedure, Manual))
                additional_transitions.append((Manual, procedure))

        # Add unidirectional transitions from recovery procedures to Manual
        if recovery_paths is not None:
            recovery_procedures = {procedure for path in recovery_paths for procedure in path}
            for procedure in recovery_procedures:
                if procedure not in procedures:
                    procedures.add(procedure)
                    additional_transitions.append((procedure, Manual))

        # Add transition for Initial -> Manual, but not the other way
        if (Initial, Manual) not in procedure_graph:
            additional_transitions.append((Initial, Manual))

        # Add transition for Fallback -> Manual, but not the other way
        additional_transitions.append((Fallback, Manual))

        procedure_graph = (*procedure_graph, *additional_transitions)
        return procedure_graph, procedures

    def resolve_parameters(self, required_parameters, user_parameters=None, check_types=True):
        try:
            _parameters = core.api.get_parameters()
        except URLError:
            raise OperationParametersNotFound("Failed fetching parameters over the HTTP API")
        parameters = {}
        for key in required_parameters:
            try:
                parameters[key] = _parameters[self.parameter_mapping[key]]
            except KeyError:
                raise OperationParametersNotFound(f"State was given an unknown key for parameter {key}")

        if user_parameters is not None:
            parameters.update(user_parameters)

        if check_types:
            for name, value in parameters.items():
                try:
                    if not check_parameter_type(value, self.parameter_types[self.parameter_mapping[name]]):
                        raise OperationParametersNotFound(
                            f"Incorrect type for {name} (expected: {self.parameter_types[self.parameter_mapping[name]]}, was: {type(value).__name__})"
                        )
                except KeyError:
                    raise OperationParametersNotFound(f"Type information not found for {name}")
        return parameters

    def recovery_operations(self) -> Iterable[Operation]:
        return [Operation([Initial] + list(recovery_path)) for recovery_path in self.recovery_paths]

    def operations(self, current_procedure) -> Iterable[Operation]:
        operations = router.available_operations(self.procedure_graph, current_procedure)
        if current_procedure.is_operation() and (loops := self.loop_procedures.get(current_procedure)):
            loop_operations = [Operation([current_procedure, *loop, current_procedure]) for loop in loops]
            operations = list(operations) + loop_operations
        return sorted(operations, key=lambda operation: (-operation.priority, operation.duration))

    def get_operation(self, current_procedure: type[Procedure], name_or_id: str):
        operations = self.operations(current_procedure)
        for op in operations:
            if name_or_id == op.static_name or name_or_id == op.id:
                return op

    def get_transitions(self):
        """
        Subset of transitions with Initial, Manual and Fallback removed, but
        loop procedures expanded.
        """
        exclude = (Initial, Manual, Fallback)
        transitions = [
            transition
            for transition in self.procedure_graph
            if transition[0] not in exclude and transition[1] not in exclude
        ]
        # Expand loop operations into graph
        for start, loops in self.loop_procedures.items():
            for loop in loops:
                transitions.append((start, loop[0]))
                for i in range(len(loop) - 1):
                    transitions.append((loop[i], loop[i + 1]))
                transitions.append((loop[-1], start))

        return transitions
