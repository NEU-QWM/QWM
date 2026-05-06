from pathlib import Path
from threading import RLock

from qualibrate.core.qualibration_node import QualibrationNode
from qualibrate.core.q_runnnable import run_modes_ctx

_nodes_by_folder = {}
_lock = RLock()


def get_graph_nodes(folder: Path):
    folder = folder.resolve()
    with _lock:
        if folder not in _nodes_by_folder:
            token = run_modes_ctx.set(None)
            try:
                _nodes_by_folder[folder] = QualibrationNode.scan_folder_for_instances(folder)
            finally:
                run_modes_ctx.reset(token)
        return _nodes_by_folder[folder]
