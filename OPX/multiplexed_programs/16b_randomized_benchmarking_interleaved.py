"""
        SINGLE QUBIT INTERLEAVED RANDOMIZED BENCHMARKING (for gates >= 40ns)
The program consists in playing random sequences of Clifford gates and measuring the state of the resonator afterwards.
Each random sequence is derived on the FPGA for the maximum depth (specified as an input) and played for each depth
asked by the user (the sequence is truncated to the desired depth). Each truncated sequence ends with the recovery gate,
found at each step thanks to a preloaded lookup table (Cayley table), that will bring the qubit back to its ground state.
In this version, a Clifford gate chosen by the user is interleaved between each random gate in the sequence. This allows
to characterize the fidelity of a specific gate.

If the readout has been calibrated and is good enough, then state discrimination can be applied to only return the state
of the qubit. Otherwise, the 'I' and 'Q' quadratures are returned.
Each sequence is played n_avg times for averaging. A second averaging is performed by playing different random sequences.

The data is then post-processed to extract the single-qubit gate fidelity and error per gate.

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit pi pulse (x180) by running qubit, spectroscopy, rabi_chevron, power_rabi and updated the config.
    - Having the qubit frequency perfectly calibrated (ramsey).
    - (optional) Having calibrated the readout (readout_frequency, amplitude, duration_optimization IQ_blobs) for better SNR.
    - Set the desired flux bias.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.plot import interrupt_on_close
from qualang_tools.bakery.randomized_benchmark_c1 import c1_table
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
delta_clifford = 10     # Play each sequence with a depth step equals to 'delta_clifford' - Must be > 0
assert (max_circuit_depth / delta_clifford).is_integer(), "max_circuit_depth / delta_clifford must be an integer."
seed = 345324           # Pseudo-random number generator seed
# Flag to enable state discrimination if the readout has been calibrated (rotated blobs and threshold)
state_discrimination = True
# List of recovery gates from the lookup table
inv_gates = [int(np.where(c1_table[i, :] == 0)[0][0]) for i in range(24)]
# index of the gate to interleave from the play_sequence() function defined below
# Correspondence table:
#  0: identity |  1: x180 |  2: y180
# 12: x90      | 13: -x90 | 14: y90 | 15: -y90 |
interleaved_gate_index = 2

# Data to save
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "num_of_sequences": num_of_sequences,
    "max_circuit_depth": max_circuit_depth,
    "delta_clifford": delta_clifford,
    "seed": seed,
    "state_discrimination": state_discrimination,
    "interleaved_gate_index": interleaved_gate_index,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################################
# Helper functions and QUA macros #
###################################
def get_interleaved_gate(gate_index):
    if gate_index == 0:
        return "I"
    elif gate_index == 1:
        return "x180"
    elif gate_index == 2:
        return "y180"
    elif gate_index == 12:
        return "x90"
    elif gate_index == 13:
        return "-x90"
    elif gate_index == 14:
        return "y90"
    elif gate_index == 15:
        return "-y90"
    else:
        return f"gate_{gate_index}"


def power_law(power, a, b, p):
    return a * (p**power) + b


def generate_sequence(interleaved_gate_index):
    cayley = declare(int, value=c1_table.flatten().tolist())
    inv_list = declare(int, value=inv_gates)
    current_state = declare(int)
    step = declare(int)
    sequence = declare(int, size=2 * max_circuit_depth + 1)
    inv_gate = declare(int, size=2 * max_circuit_depth + 1)
    i = declare(int)
    rand = Random(seed=seed)

    assign(current_state, 0)
    with for_(i, 0, i < 2 * max_circuit_depth, i + 2):
        assign(step, rand.rand_int(24))
        assign(current_state, cayley[current_state * 24 + step])
        assign(sequence[i], step)
        assign(inv_gate[i], inv_list[current_state])
        # interleaved gate
        assign(step, interleaved_gate_index)
        assign(current_state, cayley[current_state * 24 + step])
        assign(sequence[i + 1], step)
        assign(inv_gate[i + 1], inv_list[current_state])

    return sequence, inv_gate


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
    depth = declare(int)         # QUA variable for the varying depth
    depth_target = declare(int)  # QUA variable for the current depth (changes in steps of delta_clifford)
    # QUA variable to store the last Clifford gate of the current sequence which is replaced by the recovery gate
    saved_gate = declare(int)
    m = declare(int)    # QUA variable for the loop over random sequences
    n = declare(int)    # QUA variable for the averaging loop
    I = declare(fixed)  # QUA variable for the 'I' quadrature
    Q = declare(fixed)  # QUA variable for the 'Q' quadrature
    state = declare(bool)  # QUA variable for state discrimination
    # The relevant streams
    m_st = declare_stream()
    if state_discrimination:
        state_st = declare_stream()
    else:
        I_st = declare_stream()
        Q_st = declare_stream()

    with for_(m, 0, m < num_of_sequences, m + 1):  # QUA for_ loop over the random sequences
        # Generates the RB sequence with a gate interleaved after each Clifford
        sequence_list, inv_gate_list = generate_sequence(interleaved_gate_index=interleaved_gate_index)
        # depth_target is always incremented by 2 to always play gates in pairs:
        # [(random_gate - interleaved_gate)^(depth/2) - inv_gate]
        assign(depth_target, 2)
        with for_(depth, 1, depth <= 2 * max_circuit_depth, depth + 1):
            # Replacing the last gate in the sequence with the sequence's inverse gate
            assign(saved_gate, sequence_list[depth])
            assign(sequence_list[depth], inv_gate_list[depth - 1])
            # Only play the depth corresponding to target_depth
            with if_(depth == depth_target):
                with for_(n, 0, n < n_avg, n + 1):  # Averaging loop
                    wait(thermalization_time, res_key)
                    align(res_key, qubit_key)
                    with strict_timing_():
                        play_sequence(sequence_list, depth)
                    align(qubit_key, res_key)
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    if state_discrimination:
                        save(state, state_st)
                    else:
                        save(I, I_st)
                        save(Q, Q_st)
                # Always play random + interleaved gate in pairs, hence step by 2*delta_clifford
                assign(depth_target, depth_target + 2 * delta_clifford)
            # Reset the last gate of the sequence back to the original Clifford gate
            assign(sequence_list[depth], saved_gate)
        save(m, m_st)

    with stream_processing():
        m_st.save("iteration")
        if state_discrimination:
            state_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
                max_circuit_depth / delta_clifford
            ).buffer(num_of_sequences).save("state")
            state_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
                max_circuit_depth / delta_clifford
            ).average().save("state_avg")
        else:
            I_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford).buffer(
                num_of_sequences
            ).save("I")
            Q_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford).buffer(
                num_of_sequences
            ).save("Q")
            I_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford).average().save(
                "I_avg"
            )
            Q_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford).average().save(
                "Q_avg"
            )

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
    if state_discrimination:
        results = fetching_tool(job, data_list=["state_avg", "iteration"], mode="live")
    else:
        results = fetching_tool(job, data_list=["I_avg", "Q_avg", "iteration"], mode="live")
    fig = plt.figure()
    interrupt_on_close(fig, job)
    # x values: pairs of gates, so depth runs 2, 4, ..., 2*max_circuit_depth in steps of 2*delta_clifford
    x = np.arange(2, 2 * max_circuit_depth + 0.1, 2 * delta_clifford)
    while results.is_processing():
        if state_discrimination:
            state_avg, iteration = results.fetch_all()
            value_avg = state_avg
        else:
            I_avg, Q_avg, iteration = results.fetch_all()
            value_avg = I_avg
        progress_counter(iteration, num_of_sequences, start_time=results.get_start_time())
        plt.cla()
        plt.plot(x, value_avg, marker=".")
        plt.xlabel("Number of Clifford gates")
        plt.ylabel("Sequence Fidelity")
        plt.title(f"{qubit_key}, Interleaved RB [{get_interleaved_gate(interleaved_gate_index)}] ({iteration + 1}/{num_of_sequences})")
        plt.pause(0.1)

    # Fetch non-averaged results for error bars
    if state_discrimination:
        results = fetching_tool(job, data_list=["state"])
        state = results.fetch_all()[0]
        value_avg = np.mean(state, axis=0)
        error_avg = np.std(state, axis=0)
    else:
        results = fetching_tool(job, data_list=["I", "Q"])
        I, Q = results.fetch_all()
        value_avg = np.mean(I, axis=0)
        error_avg = np.std(I, axis=0)

    pars, cov = curve_fit(
        f=power_law,
        xdata=x,
        ydata=value_avg,
        p0=[0.5, 0.5, 0.9],
        bounds=(-np.inf, np.inf),
        maxfev=2000,
    )
    stdevs = np.sqrt(np.diag(cov))
    print("#########################")
    print("### Fitted Parameters ###")
    print("#########################")
    print(f"A = {pars[0]:.3} ({stdevs[0]:.1}), B = {pars[1]:.3} ({stdevs[1]:.1}), p = {pars[2]:.3} ({stdevs[2]:.1})")
    print("Covariance Matrix")
    print(cov)
    one_minus_p = 1 - pars[2]
    r_c = one_minus_p * (1 - 1 / 2**1)
    r_g = r_c / 1.875
    r_c_std = stdevs[2] * (1 - 1 / 2**1)
    r_g_std = r_c_std / 1.875
    print("#########################")
    print("### Useful Parameters ###")
    print("#########################")
    print(
        f"Error rate: 1-p = {np.format_float_scientific(one_minus_p, precision=2)} ({stdevs[2]:.1})\n"
        f"Clifford set infidelity: r_c = {np.format_float_scientific(r_c, precision=2)} ({r_c_std:.1})\n"
        f"Gate infidelity: r_g = {np.format_float_scientific(r_g, precision=2)}  ({r_g_std:.1})"
    )
    plt.figure()
    plt.errorbar(x, value_avg, yerr=error_avg, marker=".")
    plt.plot(x, power_law(x, *pars), linestyle="--", linewidth=2)
    plt.xlabel("Number of Clifford gates")
    plt.ylabel("Sequence Fidelity")
    plt.title(f"{qubit_key}, Interleaved RB [{get_interleaved_gate(interleaved_gate_index)}]")

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    if state_discrimination:
        save_data_dict.update({"state_avg_data": state})
    else:
        save_data_dict.update({"I_data": I, "Q_data": Q})
    save_data_dict.update({"fig_live": fig})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    qm.close()
