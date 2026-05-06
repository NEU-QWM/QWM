# %%
from pathlib import Path
from typing import List
from qualibrate.core.orchestration.basic_orchestrator import BasicOrchestrator
from qualibrate.core.parameters import GraphParameters
from qualibrate import QualibrationGraph
from calibration_utils.graph_node_library import get_graph_nodes

nodes = get_graph_nodes(Path(__file__).parent)


class Parameters(GraphParameters):
    qubits: List[str] = ["q1"]


g = QualibrationGraph(
    name="FixedFrequencyTransmon_Retuning",
    parameters=Parameters(),
    nodes={
        "IQ_blobs": nodes["07_iq_blobs"].copy(name="IQ_blobs"),
        "ramsey": nodes["06a_ramsey"].copy(name="ramsey", use_state_discrimination=True),
        "power_rabi_error_amplification_x180": nodes["04b_power_rabi"].copy(
            name="power_rabi_error_amplification_x180",
            max_number_pulses_per_sweep=200,
            min_amp_factor=0.98,
            max_amp_factor=1.02,
            amp_factor_step=0.002,
            use_state_discrimination=True,
        ),
        "power_rabi_error_amplification_x90": nodes["04b_power_rabi"].copy(
            name="power_rabi_error_amplification_x90",
            max_number_pulses_per_sweep=200,
            min_amp_factor=0.98,
            max_amp_factor=1.02,
            amp_factor_step=0.002,
            operation="x90",
            update_x90=False,
            use_state_discrimination=True,
        ),
        "Randomized_benchmarking": nodes["11a_single_qubit_randomized_benchmarking"].copy(
            name="Randomized_benchmarking",
            use_state_discrimination=True,
            delta_clifford=20,
            num_random_sequences=500,
        ),
    },
    connectivity=[
        ("IQ_blobs", "ramsey"),
        ("ramsey", "power_rabi_error_amplification_x180"),
        ("power_rabi_error_amplification_x180", "power_rabi_error_amplification_x90"),
        ("power_rabi_error_amplification_x90", "Randomized_benchmarking"),
    ],
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()
