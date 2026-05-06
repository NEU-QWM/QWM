from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.qpu import FixedFrequencyQuam, FluxTunableQuam
from pathlib import Path

def _project_state_path() -> Path:
    return Path(__file__).resolve().parent.parent / "quam_state"
# Define the QUAM class that will be used in all calibration nodes
# Should inherit from either FixedFrequencyQuam or FluxTunableQuam
@quam_dataclass
class Quam(FluxTunableQuam):
    pass
