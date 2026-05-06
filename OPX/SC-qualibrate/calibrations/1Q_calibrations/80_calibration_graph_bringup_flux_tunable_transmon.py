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
    name="FluxTunableTransmon_BringUp",
    parameters=Parameters(),
    nodes={
        "resonator_spectroscopy": nodes["02a_resonator_spectroscopy"].copy(name="resonator_spectroscopy"),
        # "resonator_spectroscopy_vs_power": nodes["02b_resonator_spectroscopy_vs_power"].copy(name="resonator_spectroscopy_vs_power"),
        "resonator_spectroscopy_vs_flux": nodes["02c_resonator_spectroscopy_vs_flux"].copy(
            name="resonator_spectroscopy_vs_flux"
        ),
        "qubit_spectroscopy": nodes["03a_qubit_spectroscopy"].copy(name="qubit_spectroscopy"),
        "qubit_spectroscopy_vs_flux": nodes["03b_qubit_spectroscopy_vs_flux"].copy(
            name="qubit_spectroscopy_vs_flux"
        ),
        "rabi_chevron": nodes["04a_rabi_chevron"].copy(name="rabi_chevron"),
        "power_rabi": nodes["04b_power_rabi"].copy(name="power_rabi"),
        "readout_power_optimization": nodes["08b_readout_power_optimization"].copy(
            name="readout_power_optimization"
        ),
        "readout_frequency_optimization": nodes["08a_readout_frequency_optimization"].copy(
            name="readout_frequency_optimization"
        ),
        "IQ_blobs": nodes["07_iq_blobs"].copy(name="IQ_blobs"),
        "ramsey_vs_flux_calibration": nodes["09_ramsey_vs_flux_calibration"].copy(
            name="ramsey_vs_flux_calibration"
        ),
        "power_rabi_error_amplification_x180": nodes["04b_power_rabi"].copy(
            name="power_rabi_error_amplification_x180",
            max_number_pulses_per_sweep=100,
            min_amp_factor=0.8,
            max_amp_factor=1.2,
            amp_factor_step=0.01,
            use_state_discrimination=True,
        ),
        "power_rabi_error_amplification_x90": nodes["04b_power_rabi"].copy(
            name="power_rabi_error_amplification_x90",
            max_number_pulses_per_sweep=100,
            min_amp_factor=0.8,
            max_amp_factor=1.2,
            amp_factor_step=0.01,
            operation="x90",
            update_x90=False,
            use_state_discrimination=True,
        ),
        "T1": nodes["05_T1"].copy(name="T1", use_state_discrimination=True),
        "ramsey": nodes["06a_ramsey"].copy(name="ramsey", use_state_discrimination=True),
        "T2echo": nodes["06b_echo"].copy(name="T2echo", use_state_discrimination=True),
        "DRAG_calibration": nodes["10b_drag_calibration_180_minus_180"].copy(
            name="DRAG_calibration", use_state_discrimination=True
        ),
        "Randomized_benchmarking": nodes["11a_single_qubit_randomized_benchmarking"].copy(
            name="Randomized_benchmarking", use_state_discrimination=True
        ),
    },
    connectivity=[
        # ("resonator_spectroscopy_vs_power", "resonator_spectroscopy"),
        ("resonator_spectroscopy", "resonator_spectroscopy_vs_flux"),
        ("resonator_spectroscopy_vs_flux", "qubit_spectroscopy"),
        ("qubit_spectroscopy", "qubit_spectroscopy_vs_flux"),
        ("qubit_spectroscopy_vs_flux", "rabi_chevron"),
        ("rabi_chevron", "power_rabi"),
        ("power_rabi", "readout_power_optimization"),
        ("readout_power_optimization", "readout_frequency_optimization"),
        ("readout_frequency_optimization", "IQ_blobs"),
        ("IQ_blobs", "ramsey_vs_flux_calibration"),
        ("ramsey_vs_flux_calibration", "power_rabi_error_amplification_x180"),
        ("power_rabi_error_amplification_x180", "power_rabi_error_amplification_x90"),
        ("power_rabi_error_amplification_x90", "ramsey"),
        ("ramsey", "T1"),
        ("T1", "T2echo"),
        ("T2echo", "DRAG_calibration"),
        ("DRAG_calibration", "Randomized_benchmarking"),
    ],
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()
