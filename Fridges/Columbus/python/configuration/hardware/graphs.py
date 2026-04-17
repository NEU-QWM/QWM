from . import SystemType
from configuration.hardware.CS2_GHS.graph import graph as CS2_GHS_graph
from configuration.hardware.GHS_1000.graph import graph as GHS_1000_graph


device_graphs = {
    SystemType.PYTHON_TEST: None,
    SystemType.IT: None,
    SystemType.CS2_GHS: CS2_GHS_graph,
    SystemType.GHS_250: None,
    SystemType.GHS_400: None,
    SystemType.GHS_1000: GHS_1000_graph,
    SystemType.GHS_1000_FSE: GHS_1000_graph,
}
