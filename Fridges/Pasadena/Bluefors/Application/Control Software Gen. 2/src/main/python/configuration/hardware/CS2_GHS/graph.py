from core.sentinel.graph import DeviceGraph, GraphNode, ValveNode


class Valve(ValveNode):
    V2 = "V2"
    V3 = "V3"


class Other(GraphNode):
    Air = "Air"
    B1 = "B1"
    P1 = "P1"
    P3 = "P3"
    R1 = "R1"


graph = DeviceGraph.create(
    node_classes=[Valve, Other],
    pairwise_graph=(
        (Other.P1, Other.B1),
        (Other.B1, Valve.V3),
        (Other.B1, Other.P3),
        (Valve.V3, Other.B1),
        (Valve.V3, Valve.V2),
        (Valve.V2, Other.R1),
        (Valve.V3, Other.R1),
        (Other.R1, Other.Air),
        (Valve.V2, Other.Air),
    ),
)
