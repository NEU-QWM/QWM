"""
        SINGLE QUBIT RANDOMIZED BENCHMARKING (for gates >= 20ns and < 40ns)
Because of the latency of the switch/case commands (40ns), we cannot play a random sequence of gates shorter than 40ns
using the standard RB script.
The trick is to convert the random sequence made of Clifford operations into a sequence of single qubit gates
(X, Y, X/2...) and play them by pairs. This way we can have gap-less RB with gates as short as 20ns, because 20ns+20ns=40ns.
The drawback is that the max depth is currently limited to 2600 Clifford gates due to data memory.

Here again, each random sequence is derived on the FPGA for the maximum depth (specified as an input) and played for each depth
asked by the user (the sequence is truncated to the desired depth). Each truncated sequence ends with the recovery gate,
found at each step thanks to a preloaded lookup table (Cayley table), that will bring the qubit back to its ground state.

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
max_circuit_depth = 1000  # Maximum circuit depth < 2600 (6*max_circuit_depth < 16k)
delta_clifford = 10     # Play each sequence with a depth step equals to 'delta_clifford' - Must be > 1
assert (max_circuit_depth / delta_clifford).is_integer(), "max_circuit_depth / delta_clifford must be an integer."
seed = 345324           # Pseudo-random number generator seed
# Flag to enable state discrimination if the readout has been calibrated (rotated blobs and threshold)
state_discrimination = True
# List of recovery gates from the lookup table
inv_gates = [int(np.where(c1_table[i, :] == 0)[0][0]) for i in range(24)]

# Data to save
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "num_of_sequences": num_of_sequences,
    "max_circuit_depth": max_circuit_depth,
    "delta_clifford": delta_clifford,
    "seed": seed,
    "state_discrimination": state_discrimination,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################################
# Helper functions and QUA macros #
###################################
# Single qubit Clifford operations
c1_ops = [
    ("I",),
    ("x180",),
    ("y180",),
    ("y180", "x180"),
    ("x90", "y90"),
    ("x90", "-y90"),
    ("-x90", "y90"),
    ("-x90", "-y90"),
    ("y90", "x90"),
    ("y90", "-x90"),
    ("-y90", "x90"),
    ("-y90", "-x90"),
    ("x90",),
    ("-x90",),
    ("y90",),
    ("-y90",),
    ("-x90", "y90", "x90"),
    ("-x90", "-y90", "x90"),
    ("x180", "y90"),
    ("x180", "-y90"),
    ("y180", "x90"),
    ("y180", "-x90"),
    ("x90", "y90", "x90"),
    ("-x90", "y90", "-x90"),
]
# Single qubit gates
single_qubit_gates = ["I", "x180", "x90", "-x90", "y180", "y90", "-y90"]
# Pairs of single qubit gates
single_qubit_gate_pairs = []
for i in range(len(single_qubit_gates)):
    for j in range(len(single_qubit_gates)):
        single_qubit_gate_pairs.append(((single_qubit_gates[i],) + (single_qubit_gates[j],)))


def power_law(power, a, b, p):
    return a * (p**power) + b


def single_gate_indices_from_clifford(clifford_index):
    out = []
    for gate in c1_ops[clifford_index]:
        out.append(single_qubit_gates.index(gate))
    return out


def pairs_of_gate_indices_from_single(ind1, ind2):
    for pair in single_qubit_gate_pairs:
        if pair[0] == single_qubit_gates[ind1] and pair[1] == single_qubit_gates[ind2]:
            return single_qubit_gate_pairs.index(pair)


def from_clifford_to_single(clifford_seq, single_qubit_seq, single_qubit_ind):
    with switch_(clifford_seq):
        for clifford_index in [0, 1, 2, 12, 13, 14, 15]:
            with case_(clifford_index):
                assign(single_qubit_seq[single_qubit_ind], single_gate_indices_from_clifford(clifford_index)[0])
                assign(single_qubit_ind, single_qubit_ind + 1)
        for clifford_index in [3, 4, 5, 6, 7, 8, 9, 10, 11, 18, 19, 20, 21]:
            with case_(clifford_index):
                assign(single_qubit_seq[single_qubit_ind], single_gate_indices_from_clifford(clifford_index)[0])
                assign(single_qubit_seq[single_qubit_ind + 1], single_gate_indices_from_clifford(clifford_index)[1])
                assign(single_qubit_ind, single_qubit_ind + 2)
        for clifford_index in [16, 17, 22, 23]:
            with case_(clifford_index):
                assign(single_qubit_seq[single_qubit_ind], single_gate_indices_from_clifford(clifford_index)[0])
                assign(single_qubit_seq[single_qubit_ind + 1], single_gate_indices_from_clifford(clifford_index)[1])
                assign(single_qubit_seq[single_qubit_ind + 2], single_gate_indices_from_clifford(clifford_index)[2])
                assign(single_qubit_ind, single_qubit_ind + 3)
    return single_qubit_seq, single_qubit_ind


def generate_sequence():
    print("Compute sequence...")
    cayley = declare(int, value=list(c1_table.flatten()))
    inv_list = declare(int, value=inv_gates)
    sequence = declare(int, size=max_circuit_depth + 1)
    inv_gate = declare(int, size=2 * max_circuit_depth + 1)
    rand = Random(seed=seed)

    current_state = declare(int)
    step = declare(int)
    i = declare(int)

    sequence_single = declare(int, size=2 * max_circuit_depth + 1)
    sequence_single_len = declare(int)
    sequence_single_len_prev = declare(int)

    sequence_pairs_lengths = declare(int, size=max_circuit_depth)
    even = declare(bool)
    sequence_pairs_len = declare(int)
    last = declare(int)
    first = declare(int)
    end_point = declare(int)
    ii = declare(int)

    recovery_single = declare(int, size=4)
    recovery_index_single = declare(int)
    recovery_index_pairs = declare(int)
    assign(recovery_index_pairs, 0)

    assign(current_state, 0)
    assign(sequence_single_len, 0)
    assign(sequence_pairs_len, 0)
    assign(even, True)
    with for_(i, 0, i < max_circuit_depth, i + 1):
        assign(step, rand.rand_int(24))
        assign(current_state, cayley[current_state * 24 + step])
        assign(sequence[i], step)
        assign(inv_gate[2 * i], inv_list[current_state])

        sequence_single, sequence_single_len = from_clifford_to_single(
            sequence[i], sequence_single, sequence_single_len
        )

        with if_(i == 0):
            assign(first, 0)
        with else_():
            assign(first, sequence_single_len_prev)
        assign(end_point, (sequence_single_len >> 1) << 1)

        with if_(~even):
            for j in range(len(single_qubit_gates)):
                with if_(last == j):
                    for k in range(len(single_qubit_gates)):
                        with if_(sequence_single[sequence_single_len_prev] == k):
                            assign(sequence[sequence_pairs_len], pairs_of_gate_indices_from_single(j, k))
                            assign(sequence_pairs_len, sequence_pairs_len + 1)
            assign(first, sequence_single_len_prev + 1)

        with if_(sequence_single_len == (sequence_single_len >> 1) << 1):
            assign(even, True)
        with else_():
            assign(even, False)
            assign(last, sequence_single[sequence_single_len - 1])

        with for_(ii, first, ii < end_point, ii + 2):
            for j in range(len(single_qubit_gates)):
                with if_(sequence_single[ii] == j):
                    for k in range(len(single_qubit_gates)):
                        with if_(sequence_single[ii + 1] == k):
                            assign(sequence[sequence_pairs_len], pairs_of_gate_indices_from_single(j, k))
                            assign(sequence_pairs_len, sequence_pairs_len + 1)
        assign(sequence_pairs_lengths[i], sequence_pairs_len)

        assign(recovery_index_single, 0)
        assign(recovery_single[0], 0)
        assign(recovery_single[1], 0)
        assign(recovery_single[2], 0)
        assign(recovery_single[3], 0)
        recovery_single, recovery_index_single = from_clifford_to_single(
            inv_gate[2 * i], recovery_single, recovery_index_single
        )
        with if_(even):
            with for_(ii, 0, ii < recovery_index_single, ii + 2):
                for j in range(len(single_qubit_gates)):
                    with if_(recovery_single[ii] == j):
                        for k in range(len(single_qubit_gates)):
                            with if_(recovery_single[ii + 1] == k):
                                assign(inv_gate[recovery_index_pairs], pairs_of_gate_indices_from_single(j, k))
                                assign(recovery_index_pairs, recovery_index_pairs + 1)
        with else_():
            for j in range(len(single_qubit_gates)):
                with if_(last == j):
                    for k in range(len(single_qubit_gates)):
                        with if_(recovery_single[0] == k):
                            assign(inv_gate[recovery_index_pairs], pairs_of_gate_indices_from_single(j, k))
                            assign(recovery_index_pairs, recovery_index_pairs + 1)
            with for_(ii, 1, ii < recovery_index_single, ii + 2):
                for j in range(len(single_qubit_gates)):
                    with if_(recovery_single[ii] == j):
                        for k in range(len(single_qubit_gates)):
                            with if_(recovery_single[ii + 1] == k):
                                assign(inv_gate[recovery_index_pairs], pairs_of_gate_indices_from_single(j, k))
                                assign(recovery_index_pairs, recovery_index_pairs + 1)
        with if_(recovery_index_pairs > ((recovery_index_pairs >> 1) << 1)):
            assign(inv_gate[recovery_index_pairs], 0)
            assign(recovery_index_pairs, recovery_index_pairs + 1)

        assign(sequence_single_len_prev, sequence_single_len)
    return sequence, sequence_pairs_lengths, inv_gate


def play_sequence(sequence_list, number_of_gates):
    i = declare(int)
    with for_(i, 0, i < number_of_gates, i + 1):
        with switch_(sequence_list[i], unsafe=True):
            for ii in range(len(single_qubit_gate_pairs)):
                with case_(ii):
                    for iii in range(len(single_qubit_gate_pairs[ii])):
                        if single_qubit_gate_pairs[ii][iii] == "I":
                            wait(x180_len // 4, qubit_key)
                        else:
                            play(single_qubit_gate_pairs[ii][iii], qubit_key)


###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    depth = declare(int)
    depth_target = declare(int)
    saved_gates = declare(int, size=2)
    random_sequence_index = declare(int)
    n = declare(int)
    I = declare(fixed)
    Q = declare(fixed)
    state = declare(bool)
    seq_length = declare(int)
    rnd_seq_ind_st = declare_stream()
    if state_discrimination:
        state_st = declare_stream()
    else:
        I_st = declare_stream()
        Q_st = declare_stream()

    with for_(random_sequence_index, 0, random_sequence_index < num_of_sequences, random_sequence_index + 1):
        save(random_sequence_index, rnd_seq_ind_st)
        sequence_pairs, sequence_pairs_lengths, recovery_pairs = generate_sequence()
        assign(depth_target, 0)
        with for_(depth, 1, depth <= max_circuit_depth, depth + 1):
            with if_((depth == 1) | (depth == depth_target)):
                assign(saved_gates[0], sequence_pairs[sequence_pairs_lengths[depth - 1]])
                assign(saved_gates[1], sequence_pairs[sequence_pairs_lengths[depth - 1] + 1])
                assign(sequence_pairs[sequence_pairs_lengths[depth - 1]], recovery_pairs[2 * depth - 2])
                assign(sequence_pairs[sequence_pairs_lengths[depth - 1] + 1], recovery_pairs[2 * depth - 1])
                assign(seq_length, sequence_pairs_lengths[depth - 1] + 2)
                with for_(n, 0, n < n_avg, n + 1):
                    wait(thermalization_time, res_key)
                    align(res_key, qubit_key)
                    with strict_timing_():
                        play_sequence(sequence_pairs, seq_length)
                    align(qubit_key, res_key)
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    if state_discrimination:
                        save(state, state_st)
                    else:
                        save(I, I_st)
                        save(Q, Q_st)
                assign(depth_target, depth_target + delta_clifford)
                assign(sequence_pairs[sequence_pairs_lengths[depth - 1]], saved_gates[0])
                assign(sequence_pairs[sequence_pairs_lengths[depth - 1] + 1], saved_gates[1])

    with stream_processing():
        rnd_seq_ind_st.save("iteration")
        if state_discrimination:
            state_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
                max_circuit_depth / delta_clifford + 1
            ).buffer(num_of_sequences).save("state")
            state_st.boolean_to_int().buffer(n_avg).map(FUNCTIONS.average()).buffer(
                max_circuit_depth / delta_clifford + 1
            ).average().save("state_avg")
        else:
            I_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford + 1).buffer(
                num_of_sequences
            ).save("I")
            Q_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford + 1).buffer(
                num_of_sequences
            ).save("Q")
            I_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford + 1).average().save("I_avg")
            Q_st.buffer(n_avg).map(FUNCTIONS.average()).buffer(max_circuit_depth / delta_clifford + 1).average().save("Q_avg")

#####################################
#  Open Communication with the QOP  #
#####################################
from opx_credentials import qop_ip, cluster
from qm import CompilerOptionArguments
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=100_000)
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
    x = np.arange(0, max_circuit_depth + 0.1, delta_clifford)
    x[0] = 1  # first depth is 1
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
        plt.title(f"{qubit_key}, Single qubit RB 20ns ({iteration + 1}/{num_of_sequences})")
        plt.pause(0.1)

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
    plt.title(f"{qubit_key}, Single qubit RB 20ns")

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
