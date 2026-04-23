from typing import Type
from core.state_machine.procedure import Procedure, OperationProcedure


ProcedureT = Type[Procedure]
OperationProcedureT = Type[OperationProcedure]

Transition = tuple[ProcedureT, ProcedureT]
Transitions = tuple[Transition, ...]

LoopProcedures = dict[OperationProcedureT, list[tuple[ProcedureT, ...]]]
RecoveryPaths = list[tuple[ProcedureT, ...]]
