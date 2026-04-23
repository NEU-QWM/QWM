import unittest

from core.sentinel.graph import DeviceGraph, connected, ValveNode
from configuration.hardware.CS2_GHS.graph import graph as CS2_graph, Other


class Valve(ValveNode):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


graph = dict(
    node_classes=[Valve],
    pairwise_graph=(
        (Valve.A, Valve.B),
        (Valve.B, Valve.C),
    ),
)


class TestGraph(unittest.TestCase):
    state = {"A_ENABLED": False, "B_ENABLED": False, "C_ENABLED": False, "D_ENABLED": False, "E_ENABLED": False}

    def connected(self, graph, start, end, state):
        return connected(graph, start, end, self.state | state)

    def test_graph(self):
        g = DeviceGraph.create(**graph)
        self.assertFalse(self.connected(g, *("A", "C"), {}))
        self.assertFalse(self.connected(g, *("A", "C"), {"A_ENABLED": True, "C_ENABLED": True}))
        self.assertTrue(self.connected(g, *("A", "C"), {"B_ENABLED": True}))
        self.assertTrue(self.connected(g, *("A", "C"), {"A_ENABLED": True, "B_ENABLED": True, "C_ENABLED": True}))

    def test_graph_alternate_path(self):
        g = DeviceGraph.create(
            graph["node_classes"], graph["pairwise_graph"] + ((Valve.A, Valve.D), (Valve.D, Valve.C))
        )
        self.assertFalse(self.connected(g, *("A", "C"), {}))
        self.assertFalse(self.connected(g, *("A", "C"), {"A_ENABLED": True, "C_ENABLED": True}))
        self.assertTrue(self.connected(g, *("A", "C"), {"D_ENABLED": True}))
        self.assertTrue(self.connected(g, *("A", "C"), {"A_ENABLED": True, "D_ENABLED": True, "C_ENABLED": True}))

    def test_graph_long_path(self):
        g = DeviceGraph.create(
            graph["node_classes"], graph["pairwise_graph"] + ((Valve.C, Valve.D),)
        )
        self.assertFalse(self.connected(g, *("A", "D"), {}))
        self.assertFalse(self.connected(g, *("A", "D"), {"A_ENABLED": True, "C_ENABLED": True}))
        self.assertFalse(self.connected(g, *("A", "D"), {"B_ENABLED": True}))
        self.assertFalse(self.connected(g, *("A", "D"), {"C_ENABLED": True}))
        self.assertTrue(self.connected(g, *("A", "D"), {"B_ENABLED": True, "C_ENABLED": True}))

    def test_graph_special_cases(self):
        g = DeviceGraph.create(**graph)
        self.assertTrue(self.connected(g, *("A", "A"), {}))
        self.assertFalse(self.connected(g, *("A", "Y"), {"A_ENABLED": True, "B_ENABLED": True, "C_ENABLED": True}))
        self.assertFalse(self.connected(g, *("X", "A"), {"A_ENABLED": True, "B_ENABLED": True, "C_ENABLED": True}))
        self.assertFalse(self.connected(g, *("X", "Y"), {"A_ENABLED": True, "B_ENABLED": True, "C_ENABLED": True}))


class TestGraphCS2_GHS(unittest.TestCase):
    state = {"V2_ENABLED": False, "V3_ENABLED": False}

    def test_graph(self):
        g = CS2_graph
        self.assertTrue(connected(g, *(Other.Air, Other.Air), self.state))
        self.assertFalse(connected(g, *(Other.Air, Other.B1), self.state))
        self.assertTrue(connected(g, *(Other.Air, Other.B1), self.state | {"V3_ENABLED": True}))

        self.assertTrue(connected(g, *("Air", "Air"), self.state))
        self.assertFalse(connected(g, *("Air", "B1"), self.state))
        self.assertTrue(connected(g, *("Air", "B1"), self.state | {"V3_ENABLED": True}))
