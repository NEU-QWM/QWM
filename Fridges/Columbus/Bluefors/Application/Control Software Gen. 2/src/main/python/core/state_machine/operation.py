import hashlib
import json
import uuid
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from time import perf_counter
from typing import List, Tuple, Type

import core.api
from core import utils
from core.state_machine.exceptions import ValidationError
from core.state_machine.procedure import (
    Direction,
    Fallback,
    Initial,
    Manual,
    OperationProcedure,
    Procedure,
)
from core.state_machine.typing import ProcedureT


def timethis(func, *args, n=100):
    t0 = perf_counter()
    for i in range(n):
        func(*args)
    print(perf_counter() - t0)


class ValidationCache:
    def __init__(self):
        self.procedures = {}


@dataclass
class Operation:
    path: InitVar[list[ProcedureT]]

    start: Type[Procedure] = field(init=False)
    goal: Type[OperationProcedure] = field(init=False)
    procedures: list[ProcedureT] = field(init=False)  # aka Route
    id: str = field(init=False)

    def __repr__(self):
        return f"<Operation {self.static_name}, start: {self.start.name}, procs: {[proc.name for proc in self.procedures]}, goal: {self.goal.name}>"

    def __post_init__(self, path):
        if not path[-1].is_operation():
            raise Exception("Operations must end in OperationProcedure")
        else:
            self.start = path[0]
            self.goal = path[-1]
            self.procedures = path[1:]
            self.id = self.get_id()

    def get_id(self):
        procedures = [self.start.name] + [p.name for p in self.procedures]
        return hashlib.md5(json.dumps(utils.serialize(procedures), sort_keys=True).encode("utf-8")).hexdigest()

    @property
    def static_name(self):
        return self.goal.operation_name if not self.is_loop else self.procedures[0].name

    def dynamic_name(self, parameters, state):
        if (dynamic_name := self.goal.display_name(self, parameters, state)) is not None:
            return dynamic_name
        return self.static_name

    @property
    def direction(self):
        """
        In real life usage, the router should filter out operations that
        contain both WARMING and COOLING procedures.
        """
        if all([procedure.direction == Direction.NEITHER for procedure in self.procedures]):
            return Direction.NEITHER
        if all([procedure.direction >= Direction.NEITHER for procedure in self.procedures]):
            return Direction.WARMING
        elif all([procedure.direction <= Direction.NEITHER for procedure in self.procedures]):
            return Direction.COOLING
        return Direction.NEITHER

    @property
    def is_loop(self):
        return self.start == self.goal

    @property
    def parameters(self):
        return {parameter for procedure in self.procedures for parameter in procedure.required_parameters}

    @property
    def priority(self):
        return self.goal.priority

    @property
    def duration(self):
        if not self.is_loop:
            return sum([procedure.penalty.total_seconds() for procedure in self.procedures])
        else:
            return sum([procedure.penalty.total_seconds() for procedure in self.procedures[0:-1]])

    @property
    def serialized_procedures(self):
        return [self.start.as_map()] + [procedure.as_map() for procedure in self.procedures]

    @classmethod
    def manual(cls):
        return cls([Initial, Manual])

    @classmethod
    def fallback(cls):
        return cls([Initial, Fallback])

    def bind_parameters(self, parameters, parameter_mapping):
        self._bound_parameters = {key: parameters[key] for key in self.parameters}
        self._parameter_mapping = parameter_mapping

    def _validate(self, current_procedure=None, state=None) -> Tuple[List[ValidationError], List[ValidationError]]:
        if state is None:
            state = core.api.state
        if current_procedure is None:
            current_procedure = self.procedures[0]

        procedure_errors = list(current_procedure().validate(self._bound_parameters, state))
        operation_errors = list(self.goal().validate_operation(self.start, self, self._bound_parameters, state))
        return procedure_errors, operation_errors

    def validate(self, current_procedure=None, state=None) -> bool:
        procedure_errors, operation_errors = self._validate(current_procedure, state)
        return not procedure_errors and not operation_errors

    @staticmethod
    def serialize_parameters(parameters, parameter_mapping):
        return {
            key: {
                "value": value,
                "default": {"mapping": parameter_mapping[key]},
            }
            for key, value in parameters.items()
        }

    @staticmethod
    def serialize_validations(procedure_errors: List[ValidationError], operation_errors: List[ValidationError]):
        return {
            "procedure_errors": [v.message for v in procedure_errors],
            "operation_errors": [v.message for v in operation_errors],
        }

    def serialize(self, include_validations=True, state=None):
        """
        Corresponds to OperationInfoDto.
        """
        if state is None:
            state = core.api.state
        if include_validations:
            procedure_errors, operation_errors = self._validate(state=state)
            return {
                "operationId": self.id,
                "name": self.dynamic_name(self._bound_parameters, state),
                "staticName": self.static_name,
                "duration": float(self.duration),
                "parameters": self.serialize_parameters(self._bound_parameters, self._parameter_mapping),
                "procedures": self.serialized_procedures,
                "valid": (not procedure_errors and not operation_errors),
                "validations": self.serialize_validations(procedure_errors, operation_errors),
            }
        else:
            return {
                "operationId": self.id,
                "name": self.dynamic_name(self._bound_parameters, state),
                "staticName": self.static_name,
                "duration": float(self.duration),
                "parameters": self.serialize_parameters(self._bound_parameters, self._parameter_mapping),
                "procedures": self.serialized_procedures,
            }


@dataclass
class RunningOperation:
    operation: Operation
    parameters: dict
    current_procedure: Type[Procedure]
    dynamic_name: str
    original_start_time: datetime = field(default_factory=lambda: utils.tznow())
    running: bool = False
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    # Not used for comparison (in tests):
    start_time: datetime = field(default_factory=lambda: utils.tznow(), compare=False)
    _elapsed_time_in_seconds: float = field(default=0, compare=False)
    current_procedure_start_time: datetime = field(default_factory=lambda: utils.tznow())

    @classmethod
    def start(cls, operation: Operation, parameters: dict, state=None) -> "RunningOperation":
        if state is None:
            state = core.api.state
        dynamic_name = operation.dynamic_name(parameters, state)
        return cls(operation, parameters, operation.procedures[0], dynamic_name)

    @property
    def elapsed_time_in_seconds(self):
        return self._elapsed_time_in_seconds + (utils.tznow() - self.start_time).seconds

    @property
    def procedures(self) -> list[dict]:
        if self.operation.is_loop:
            procedures = self.operation.serialized_procedures
            procedures[0]["name"] += " (start)"
            return procedures
        else:
            return self.operation.serialized_procedures

    def run(self, interrupt_event):
        self.running = True
        _procedure = None
        core.api.persist_operation(self)
        procedures = self.remaining_procedures()
        for procedure in procedures:
            self.current_procedure = procedure
            _procedure = procedure(interrupt_event, self.parameters, self)
            # Don't re-run the OperationProcedure for loop operations
            if not (self.operation.is_loop and procedure == self.operation.goal):
                self.current_procedure_start_time = utils.tznow()
                _procedure.run()
        self.running = False
        core.api.persist_operation(self, log=True)
        if _procedure and _procedure.is_operation():
            _procedure.idle(self.parameters)

    def serialize(self):
        """
        Corresponds to OperationStateDto and "values"/"valuesPending" in
        database, used in recovery and for websocket updates.
        """
        return {
            "uuid": self.uuid,
            "operationId": self.operation.id,
            "name": self.dynamic_name,
            "staticName": self.operation.static_name,
            "startProcedure": self.operation.start.name,
            "parameters": self.parameters,
            "procedures": self.procedures,
            "state": "RUNNING" if self.running else "IDLE",
            "startDatetime": self.start_time,
            "originalStartDatetime": self.original_start_time,
            "elapsedTimeInSeconds": self.elapsed_time_in_seconds,
            "currentProcedure": self.current_procedure.name,
            "currentProcedureStartTime": self.current_procedure_start_time,
        }

    def serialize_to_automation_event(self):
        """
        Corresponds to AutomationEventRequestDTO, saved to database.
        """
        return {
            "uuid": self.uuid,
            "operationId": self.operation.id,
            "name": self.dynamic_name,
            "startProcedure": self.operation.start.name,
            "parameters": self.parameters,
            "procedures": self.procedures,
            "state": "RUNNING" if self.running else "IDLE",
            "startDatetime": self.start_time,
            "elapsedTimeInSeconds": self.elapsed_time_in_seconds,
            "currentProcedure": self.current_procedure.name,
        }

    def serialize_to_plc(self) -> dict[str, str]:
        return {
            "sStateMachineLatestOperation": self.dynamic_name,
            "sStateMachineLatestOperationTimestamp": self.start_time.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "sStateMachineLatestState": self.current_procedure.name,
            "sStateMachineLatestStateTimestamp": self.current_procedure_start_time.isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z"),
        }

    @classmethod
    def deserialize(cls, operation_map, procedures, procedure_graph) -> "RunningOperation|None":
        procedures_dict = {procedure.name: procedure for procedure in procedures}
        try:
            path = [procedures_dict[operation_map["startProcedure"]]]
            path += [procedures_dict[procedure["name"]] for procedure in operation_map["procedures"][1:]]

            class_dict = {
                "operation": Operation(path),
                "parameters": operation_map["parameters"],
                "current_procedure": procedures_dict[operation_map["currentProcedure"]],
                "original_start_time": operation_map["originalStartDatetime"],
                "running": False,
                "uuid": operation_map["uuid"],
                # "last_start_time"
                "_elapsed_time_in_seconds": operation_map["elapsedTimeInSeconds"],
                "current_procedure_start_time": operation_map.get("currentProcedureStartTime"),  # Can be None
                "dynamic_name": operation_map["name"]
            }
            if class_dict["operation"].id != operation_map["operationId"]:
                return None
        except KeyError:
            # Can happen if operation_map has a procedure name that doesn't
            # exist in current graph, or if the serialization changes
            return None

        return cls(**class_dict)

    def remaining_procedures(self):
        current_index = self.operation.procedures.index(self.current_procedure)
        return self.operation.procedures[current_index:]

    def find_valid_start_procedure(self):
        self.operation._bound_parameters = self.parameters
        current_index = self.operation.procedures.index(self.current_procedure)
        # Iterate from the current index backwards
        for procedure in self.operation.procedures[current_index::-1]:
            if self.operation.validate(procedure):
                return procedure
