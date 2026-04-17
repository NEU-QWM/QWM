import logging
from typing import Iterable

from core.state_machine.operation import Operation
from core.state_machine.procedure import (
    Direction,
    Initial,
    Manual,
    Procedure,
)
from core.state_machine.typing import Transitions

logger = logging.getLogger(__name__)


def valid_path(route, reverse):
    """
    If Manual is in route:
        1) it must be the starting procedure
        2) the length of the path must be 2, i.e. Procedure -> Manual

    Paths must end in OperationProcedure.
    If reverse=True, paths must end in Initial procedure.
    """
    if reverse:
        return route[-1] == Initial
    else:
        if (Manual not in route[1:] or len(route) == 2) and route[-1].is_operation():
            # Don't include the current procedure in the directionality check
            if all([procedure.direction >= Direction.NEITHER for procedure in route[1:]]) or all(
                [procedure.direction <= Direction.NEITHER for procedure in route[1:]]
            ):
                return True
        return False


def available_operations(graph: Transitions, from_procedure: type[Procedure], reverse=False) -> Iterable[Operation]:
    """
    Returns all reachable Operations from a given procedure.
    """
    for path in find_paths(graph, from_procedure, reverse=reverse):
        yield Operation(path if not reverse else path[::-1])


def find_paths(
    graph: Transitions, node: type[Procedure], path=[], reverse=False, stack=None
) -> Iterable[list[type[Procedure]]]:
    """
    Depth first search traversing the statemachine's graph.

    Yields a path for each valid operation encountered.
    """
    if node not in path:
        path = path.copy()
        path.append(node)

        if len(path) > 1:
            if valid_path(path, reverse):
                yield path

        for child in children(graph, node, reverse):
            if len(path) == 1 or node not in (Initial, Manual):
                yield from find_paths(graph, child, path, reverse, stack)

        if stack is not None and node not in stack:
            stack.append(node)


def children(graph, from_procedure: type[Procedure], reverse=False):
    """
    Returns list of children that can be accessed from the given procedure.
    """
    children = []
    if reverse:
        for to, _from in graph:
            if _from == from_procedure:
                children.append(to)
    else:
        for _from, to in graph:
            if _from == from_procedure:
                children.append(to)
    return children
