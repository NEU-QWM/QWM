"""
        PURITY RANDOMIZED BENCHMARKING (for gates >= 40ns)

Purity Randomized Benchmarking (also known as Unitarity RB) characterizes gate noise by measuring
the unitarity - a value between 0 and 1 that indicates how coherent the noise is:
    - Unitarity = 1: Purely coherent errors (calibration issues, over/under rotations)
    - Unitarity = 0: Purely incoherent errors (depolarization, decoherence)

Based on Wallman et al. "Estimating the Coherence of Noise" (arXiv:1503.07865).

Protocol Overview:
    The program plays random sequences of Clifford gates WITHOUT a recovery gate (unlike standard RB).
    For each sequence at each depth, all three Pauli operators (X, Y, Z) are measured to compute the
    shifted purity P = <X>^2 + <Y>^2 + <Z>^2, which measures the squared length of the Bloch vector.

    The purity decays as: E[P] = A * u^(m-1) + B
    where 'u' is the unitarity (decay constant), 'm' is the sequence length, and A, B account for SPAM errors.

Key Differences from Standard RB (15_RB.py):
    - No recovery gate: Standard RB requires it, Purity RB does NOT
    - Measurement: Standard RB measures Z only (survival probability), Purity RB measures X, Y, Z
    - Output metric: Standard RB gives sequence fidelity, Purity RB gives shifted purity
    - Decay fit: Standard RB extracts fidelity 'p', Purity RB extracts unitarity 'u'

Output Metrics:
    - Unitarity (u): Decay constant in [0, 1] indicating coherence of noise
    - Lower bound on optimal infidelity: R >= (d-1)/d * (1 - sqrt(u)) per Wallman Eq. 46

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit pi pulse (x180) by running qubit, spectroscopy, rabi_chevron, power_rabi and updated the config.
    - Having the qubit frequency perfectly calibrated (ramsey).
    - Having calibrated the readout for state discrimination (rotated blobs and threshold).
    - Set the desired flux bias.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.plot import interrupt_on_close
from macros import readout_macro
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_relaxation", "ge_threshold", "x180_len"]
res_key, readout_len, qubit_relaxation, ge_threshold, x180_len = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles

num_of_sequences = 50   # Number of random sequences
n_avg = 20              # Number of averaging loops for each random sequence
max_circuit_depth = 1000  # Maximum circuit depth
delta_clifford = 10     # Play each sequence with a depth step equal to 'delta_clifford' - Must be > 0
assert (max_circuit_depth / delta_clifford).is_integer(), "max_circuit_depth / delta_clifford must be an integer."
seed = 345324           # Pseudo-random number generator seed

# Data to save
save_data_dict = {
    "qubit_key": qubit_key,
    "num_of_sequences": num_of_sequences,
    "n_avg": n_avg,
    "max_circuit_depth": max_circuit_depth,
    "delta_clifford": delta_clifford,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################################
# Helper functions and QUA macros #
###################################
def power_law(depth, a, b, u):
    """Purity decay model: P(m) = A * u^m + B where u is unitarity."""
    return a * (u**depth) + b


def generate_sequence():
    """Generate random Clifford sequence without recovery gate (Purity RB)."""
    sequence = declare(int, size=max_circuit_depth)
    i = declare(int)
    rand = Random(seed=seed)

    with for_(i, 0, i < max_circuit_depth, i + 1):
        assign(sequence[i], rand.rand_int(24))

    return sequence


def play_sequence(sequence_list, depth):
    i = declare(int)
    with for_(i, 0, i <= depth, i + 1):
        with switch_(sequence_list[i], unsafe=True):
            with case_(0):
                wait(x180_len // 4, qubit_key)
            with case_(1):
                play("x180", qubit_key)
            with case_(2):
                play("y180", qubit_key)
            with case_(3):
                play("y180", qubit_key)
                play("x180", qubit_key)
            with case_(4):
                play("x90", qubit_key)
                play("y90", qubit_key)
            with case_(5):
                play("x90", qubit_key)
                play("-y90", qubit_key)
            with case_(6):
                play("-x90", qubit_key)
                play("y90", qubit_key)
            with case_(7):
                play("-x90", qubit_key)
                play("-y90", qubit_key)
            with case_(8):
                play("y90", qubit_key)
                play("x90", qubit_key)
            with case_(9):
                play("y90", qubit_key)
                play("-x90", qubit_key)
            with case_(10):
                play("-y90", qubit_key)
                play("x90", qubit_key)
            with case_(11):
                play("-y90", qubit_key)
                play("-x90", qubit_key)
            with case_(12):
                play("x90", qubit_key)
            with case_(13):
                play("-x90", qubit_key)
            with case_(14):
                play("y90", qubit_key)
            with case_(15):
                play("-y90", qubit_key)
            with case_(16):
                play("-x90", qubit_key)
                play("y90", qubit_key)
                play("x90", qubit_key)
            with case_(17):
                play("-x90", qubit_key)
                play("-y90", qubit_key)
                play("x90", qubit_key)
            with case_(18):
                play("x180", qubit_key)
                play("y90", qubit_key)
            with case_(19):
                play("x180", qubit_key)
                play("-y90", qubit_key)
            with case_(20):
                play("y180", qubit_key)
                play("x90", qubit_key)
            with case_(21):
                play("y180", qubit_key)
                play("-x90", qubit_key)
            with case_(22):
                play("x90", qubit_key)
                play("y90", qubit_key)
                play("x90", qubit_key)
            with case_(23):
                play("-x90", qubit_key)
                play("y90", qubit_key)
                play("-x90", qubit_key)


###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    depth = declare(int)
    depth_target = declare(int)
    m = declare(int)    # Loop over random sequences
    n = declare(int)    # Averaging loop
    c = declare(int)    # Pauli projection: 0=X, 1=Y, 2=Z
    I = declare(fixed)
    Q = declare(fixed)
    state = declare(bool)
    m_st = declare_stream()
    state_X_st = declare_stream()
    state_Y_st = declare_stream()
    state_Z_st = declare_stream()

    with for_(m, 0, m < num_of_sequences, m + 1):
        sequence_list = generate_sequence()
        assign(depth_target, 1)
        with for_(depth, 1, depth <= max_circuit_depth, depth + 1):
            with if_(depth == depth_target):
                with for_(n, 0, n < n_avg, n + 1):
                    # Measure X projection: apply -y90 before measurement
                    wait(thermalization_time, res_key)
                    align(res_key, qubit_key)
                    with strict_timing_():
                        play_sequence(sequence_list, depth)
                    play("-y90", qubit_key)
                    align(qubit_key, res_key)
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    save(state, state_X_st)

                    # Measure Y projection: apply x90 before measurement
                    wait(thermalization_time, res_key)
                    align(res_key, qubit_key)
                    with strict_timing_():
                        play_sequence(sequence_list, depth)
                    play("x90", qubit_key)
                    align(qubit_key, res_key)
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    save(state, state_Y_st)

                    # Measure Z projection directly
                    wait(thermalization_time, res_key)
                    align(res_key, qubit_key)
                    with strict_timing_():
                        play_sequence(sequence_list, depth)
                    align(qubit_key, res_key)
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    save(state, state_Z_st)

                assign(depth_target, depth_target + delta_clifford)
        save(m, m_st)

    with stream_processing():
        m_st.save("iteration")
        # Average over n_avg for each depth and sequence
        state_X_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
            max_circuit_depth / delta_clifford
        ).buffer(num_of_sequences).save("state_X")
        state_Y_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
            max_circuit_depth / delta_clifford
        ).buffer(num_of_sequences).save("state_Y")
        state_Z_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
            max_circuit_depth / delta_clifford
        ).buffer(num_of_sequences).save("state_Z")
        state_X_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
            max_circuit_depth / delta_clifford
        ).average().save("state_X_avg")
        state_Y_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
            max_circuit_depth / delta_clifford
        ).average().save("state_Y_avg")
        state_Z_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
            max_circuit_depth / delta_clifford
        ).average().save("state_Z_avg")

#####################################
#  Open Communication with the QOP  #
#####################################
from opx_credentials import qop_ip, cluster
from qm import CompilerOptionArguments
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=2_000)
    job = qmm.simulate(config, prog, simulation_config, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    samples = job.get_simulated_samples()
    samples.con1.plot()
    waveform_report = job.get_simulated_waveform_report()
    waveform_dict = waveform_report.to_dict()
    waveform_report.create_plot(samples, plot=True, save_path=str(Path(__file__).resolve()))
else:
    qm = qmm.open_qm(config, close_other_machines=True, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    job = qm.execute(prog)
    results = fetching_tool(job, data_list=["state_X_avg", "state_Y_avg", "state_Z_avg", "iteration"], mode="live")
    fig = plt.figure()
    interrupt_on_close(fig, job)
    x = np.arange(1, max_circuit_depth + 0.1, delta_clifford)
    while results.is_processing():
        state_X_avg, state_Y_avg, state_Z_avg, iteration = results.fetch_all()
        progress_counter(iteration, num_of_sequences, start_time=results.get_start_time())
        # Convert from (0,1) to (-1,1) convention for Bloch vector
        sx = 2 * state_X_avg - 1
        sy = 2 * state_Y_avg - 1
        sz = 2 * state_Z_avg - 1
        purity = sx**2 + sy**2 + sz**2
        plt.cla()
        plt.plot(x, purity, marker=".")
        plt.xlabel("Number of Clifford gates")
        plt.ylabel("Purity (|Bloch vector|²)")
        plt.title(f"{qubit_key}, Purity RB ({iteration + 1}/{num_of_sequences})")
        plt.pause(0.1)

    # Fetch full non-averaged data for error bars
    results = fetching_tool(job, data_list=["state_X", "state_Y", "state_Z"])
    state_X, state_Y, state_Z = results.fetch_all()
    sx_all = 2 * state_X - 1
    sy_all = 2 * state_Y - 1
    sz_all = 2 * state_Z - 1
    purity_all = sx_all**2 + sy_all**2 + sz_all**2
    purity_avg = np.mean(purity_all, axis=0)
    purity_err = np.std(purity_all, axis=0)

    # Fit purity decay to extract unitarity
    try:
        pars, cov = curve_fit(
            f=power_law,
            xdata=x,
            ydata=purity_avg,
            p0=[1.0, 0.0, 0.9],
            bounds=([0, 0, 0], [np.inf, np.inf, 1]),
            maxfev=5000,
        )
        stdevs = np.sqrt(np.diag(cov))
        unitarity = pars[2]
        print("#########################")
        print("### Fitted Parameters ###")
        print("#########################")
        print(f"A = {pars[0]:.3f} ± {stdevs[0]:.3f}")
        print(f"B = {pars[1]:.3f} ± {stdevs[1]:.3f}")
        print(f"u (unitarity) = {unitarity:.4f} ± {stdevs[2]:.4f}")
        # Lower bound on infidelity (single qubit: d=2)
        r_lower = (1 - 1/2) * (1 - np.sqrt(unitarity))
        print(f"Lower bound infidelity per gate: R >= {r_lower:.4f}")
        plt.figure()
        plt.errorbar(x, purity_avg, yerr=purity_err, marker=".", label="Data")
        plt.plot(x, power_law(x, *pars), linestyle="--", linewidth=2, label=f"Fit (u={unitarity:.3f})")
        plt.xlabel("Number of Clifford gates")
        plt.ylabel("Purity (|Bloch vector|²)")
        plt.title(f"{qubit_key}, Purity RB")
        plt.legend()
    except Exception as e:
        print(f"Fit failed: {e}")

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"state_X_data": state_X, "state_Y_data": state_Y, "state_Z_data": state_Z})
    save_data_dict.update({"fig_live": fig})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    qm.close()
