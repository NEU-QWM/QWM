from dataclasses import dataclass
from typing import Optional

from core.state_machine.state_machine import StateMachine
from core.state_machine.typing import LoopProcedures, RecoveryPaths, Transitions


@dataclass
class StateMachineConfig:
    name: str
    transitions: Transitions
    parameter_mapping: dict
    loop_procedures: Optional[LoopProcedures] = None
    recovery_paths: Optional[RecoveryPaths] = None

    def sm(self):
        """
        A convenience method to get a StateMachine from config.
        """
        return StateMachine(self, start=False)
