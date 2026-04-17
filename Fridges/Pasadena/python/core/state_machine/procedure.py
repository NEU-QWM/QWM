from __future__ import annotations

import logging
import time
from datetime import timedelta
from enum import Enum
from functools import total_ordering
from typing import TYPE_CHECKING, Iterable, List, Optional, final

import core.api
from core.device.command import AlertCommand, StateMachineError
from core.device.command_queue import CommandQueue
from core.state_machine.exceptions import ProcedureError, ProcStoppedException, ValidationError
from core.utils import tznow

if TYPE_CHECKING:
    from core.state_machine.operation import Operation

logger = logging.getLogger()


PERSISTENCE_MAX_TIMEOUT_DEFAULT = 15


@total_ordering
class Direction(Enum):
    """
    Used for ordering procedures for logical directions of cooldown or warmup
    """

    COOLING = -1
    NEITHER = 0
    WARMING = 1

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class Stopwatch:
    """Simple stopwatch implementation to get the number of seconds
    elapsed since the creation of the Stopwatch instance."""

    def __init__(self):
        self.start_time = time.time()

    @property
    def elapsed(self):
        """Get the number of seconds elapsed since the creation of the instance."""
        return time.time() - self.start_time


class Procedure:
    """
    An executable entity within the StateMachine, usually referred to as a
    state machine 'state' outside this project.
    """

    name: str
    penalty: timedelta = timedelta(seconds=0)
    image_url: Optional[str] = None
    required_parameters: List[str] = []
    direction: Direction = Direction.NEITHER

    def __init__(self, interrupt_event=None, parameters={}, operation=None):
        self.interrupt_event = interrupt_event
        self.parameters = parameters
        self.operation = operation
        self.stopwatch = Stopwatch
        self.last_update = tznow()
        self.command_queue = CommandQueue()

        # XXX
        # self.persistence_max_timeout = core.api.state["statemachine.persistenceMaxTimeout"] or PERSISTENCE_MAX_TIMEOUT_DEFAULT

    def run(self):
        if self.operation:
            core.api.persist_operation(self.operation, log=True)
        if errors := list(self.validate(self.parameters, core.api.state)):
            core.api.alert(AlertCommand.from_error_list(errors, self))
            raise errors[0]
        try:
            self.enter(self.parameters)
            self.command_queue.execute_queued_commands()

            self.procedure(self.parameters)
            if not self.command_queue.empty:
                raise ProcedureError(1649, "Check that you executed command queue in procedure method")

            self.exit(self.parameters)
        except ProcedureError as e:
            core.api.alert(AlertCommand.from_error(e, self))
            raise e

    def wait(self, seconds):
        """
        Can be used to wait for device commands to execute, or just for time to
        pass when some actions of the Procedure require real-world time to
        pass.

        Meanwhile, the period is used to persist the currently running
        operation to the database. After the operation status has been updated,
        the system waits until the time given as parameter has passed before
        returning.

        The wait can be interrupted by setting the interrupt_event attribute of
        the Procedure.
        """

        # If self.interrupt_event or self.operation are not given, as is
        # usually the case for validate method calls, this method should not be
        # called
        if not self.interrupt_event or not self.operation:
            raise ProcedureError(-1, "You shouldn't use Procedure.wait in validate")

        logging.debug(f"waiting {seconds} seconds")

        persistence_max_timeout = (
            core.api.get_parameter("persistenceMaxTimeout", False) or PERSISTENCE_MAX_TIMEOUT_DEFAULT
        )
        if (tznow() - self.last_update).total_seconds() > persistence_max_timeout:
            self.last_update = tznow()
            core.api.persist_operation(self.operation)

        self.interrupt_event.wait(seconds)

        if self.interrupt_event.is_set():
            logging.debug("Procedure stopped while waiting, returning immediately")
            raise ProcStoppedException

    @classmethod
    def as_map(cls):
        if not cls.image_url:
            return {"name": cls.name}
        else:
            return {"name": cls.name, "imageUrl": cls.image_url}

    @classmethod
    def is_operation(cls):
        return issubclass(cls, OperationProcedure)

    def validate(self, parameters, state) -> Iterable[ValidationError]:
        """
        Validates if ok to enter the Procedure
        """
        return iter(())

    def enter(self, parameters):
        """
        Cleanup-code making entering state "clean". Here it is possible to
        gather commands in to the command queue, which are then run after all
        commands have been gathered
        """

    def exit(self, parameters):
        """
        cleanup-code making exiting state "clean"
        """

    def procedure(self, parameters):
        """
        Actual code to run main business logic
        """

    def __str__(self):
        return f"Procedure {self.name} (penalty {self.penalty})"


class OperationProcedure(Procedure):
    """
    OperationProcedures are Procedures, in which the StateMachine may end up
    in, i.e. it is a goal Procedure. They have an additional name and
    validation for the operation.
    """

    operation_name: str
    priority: int = 0

    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "operation_name"):
            raise TypeError(f"Please define operation_name in {cls.name} ({cls})")
        return super().__init_subclass__(**kwargs)

    @classmethod
    def display_name(cls, operation: Operation, parameters, state) -> None|str:
        return None

    def validate_operation(self, from_procedure, operation, parameters, state) -> Iterable[ValidationError]:
        """
        Validates if ok to start a set of Procedures ending in this OperationProcedure
        """
        return iter(())

    def idle(self, parameters):
        """
        Runs after Procedure.exit(). Can be used to maintain state while idling
        in an OperationProcedure. Include a call to Procedure.wait() if running
        an infinite loop to make sure it is interruptible.
        """
        pass


# All StateMachines must implement Initial and Manual Procedures


@final
class Initial(Procedure):
    name = "Initial"
    penalty = timedelta(hours=0.0)
    image_url = None


@final
class Manual(OperationProcedure):
    name = "Manual"
    operation_name = "Manual"
    penalty = timedelta(hours=0.0)
    image_url = "images/Manual_Mode.mp4"
    priority = -1


@final
class Fallback(OperationProcedure):
    name = "Fallback"
    operation_name = "Fallback"
    penalty = timedelta(hours=0.0)
    image_url = "images/Manual_Mode.mp4"
    priority = -1
