from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, EnumMeta
from typing import Literal


class ABCEnumMeta(EnumMeta, ABCMeta):
    """
    Metaclass that combines EnumMeta and ABCMeta, since classes can't have two
    different metaclasses.
    """

    pass


class AbstractGraphNode(Enum, metaclass=ABCEnumMeta):
    @abstractmethod
    def enabled(self, state) -> Literal[True] | Literal[False]:
        pass


class ValveNode(AbstractGraphNode):
    """
    Type of node that checks against given dictionary argument state if a
    device by its name is enabled or not.
    """
    def enabled(self, state):
        return state.get(f"{self.name}_ENABLED", True)


class GraphNode(AbstractGraphNode):
    """
    Graph nodes that are not valves, and are treated as if they are always
    open.
    """
    def enabled(self, state):
        return True


@dataclass(frozen=True)
class DeviceGraph:
    node_classes: list[AbstractGraphNode]
    graph: dict[AbstractGraphNode, list[AbstractGraphNode]]

    @classmethod
    def create(cls, node_classes, pairwise_graph):
        return cls(node_classes, pairwise_connections_to_dict(pairwise_graph))

    def get(self, node_name) -> None | AbstractGraphNode:
        for _class in self.node_classes:
            try:
                return _class(node_name)
            except ValueError:
                pass


def pairwise_connections_to_dict(graph):
    """
    Converts pairwise defined graph to a dict, where each device exists as a
    key and the value is a list of immediately connected devices.
    """
    d = {}
    for key, val in graph:
        if val not in d.setdefault(key, []):
            d.setdefault(key, []).append(val)
        if key not in d.setdefault(val, []):
            d.setdefault(val, []).append(key)
    return d


def find_path(
    graph: dict[AbstractGraphNode, list[AbstractGraphNode]],
    state: dict,
    node: AbstractGraphNode,
    end: AbstractGraphNode,
    path: list[AbstractGraphNode],
):
    """
    Depth-first search to find connections between nodes, i.e. devices in our
    case.
    """
    path = path.copy()
    path.append(node)
    for child in graph[node]:
        # This check needs to be here, since we don't require the endpoint to pass enabled-check
        if child == end:
            path.append(end)
            return path
        elif child not in path and child.enabled(state):
            p = find_path(graph, state, child, end, path)
            if p is not None:
                return p
    return None


def connected(graph: DeviceGraph, start: str | AbstractGraphNode, end: str | AbstractGraphNode, state):
    if start == end:
        return True
    if type(start) is str and type(end) is str:
        start_node = graph.get(start)
        end_node = graph.get(end)
        if start_node is None or end_node is None:
            return False
    else:
        start_node = start
        end_node = end

    if start_node not in graph.graph or end_node not in graph.graph:
        return False
    else:
        p = find_path(graph.graph, state, start_node, end_node, [])
        return p is not None
