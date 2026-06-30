"""
        DRAG PULSE CALIBRATION (YALE METHOD)
The sequence consists in applying successively x180-y90 and y180-x90 to the qubit while varying the DRAG
coefficient alpha. The qubit is reset to the ground state between each sequence and its state is measured and stored.
Each sequence will bring the qubit to the same state only when the DRAG coefficient is set to its correct value.

This protocol is described in Reed's thesis (Fig. 5.8) https://rsl.yale.edu/sites/default/files/files/RSL_Theses/reed.pdf
This protocol was also cited in: https://doi.org/10.1103/PRXQuantum.2.040202

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit pi pulse (x180) by running qubit, spectroscopy, rabi_chevron, power_rabi and updated the config.
    - (optional) Having calibrated the readout (readout_frequency, amplitude, duration_optimization IQ_blobs) for better SNR.
    - Set the DRAG coefficient to a non-zero value in the config: such as drag_coef = 1
    - Set the desired flux bias.

Next steps before going to the next node:
    - Update the DRAG coefficient (drag_coef) in the configuration.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.plot import interrupt_on_close
from qualang_tools.loops import from_array
from macros import readout_macro
import matplotlib.pyplot as plt
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
n_avg = 100_000  # Number of averaging loops
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_relaxation", "ge_threshold", "drag_coef"]
res_key, readout_len, qubit_relaxation, ge_threshold, drag_coef = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles

# Scan the DRAG coefficient pre-factor
a_min = -1.0
a_max = 1.0
da = 0.1
amps = np.arange(a_min, a_max + da / 2, da)  # + da/2 to add a_max to amplitudes

# Check that the DRAG coefficient is not 0
assert drag_coef != 0, "The DRAG coefficient 'drag_coef' must be different from 0 in the config."

# Data to save
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "amps": amps,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)      # QUA variable for the averaging loop
    a = declare(fixed)    # QUA variable for the DRAG coefficient pre-factor
    I = declare(fixed)    # QUA variable for the measured 'I' quadrature
    Q = declare(fixed)    # QUA variable for the measured 'Q' quadrature
    state = declare(bool)  # QUA variable for the qubit state
    I1_st = declare_stream()      # Stream for the 'I' quadrature for the 1st sequence x180-y90
    Q1_st = declare_stream()      # Stream for the 'Q' quadrature for the 1st sequence x180-y90
    I2_st = declare_stream()      # Stream for the 'I' quadrature for the 2nd sequence y180-x90
    Q2_st = declare_stream()      # Stream for the 'Q' quadrature for the 2nd sequence y180-x90
    state1_st = declare_stream()  # Stream for the qubit state for the 1st sequence x180-y90
    state2_st = declare_stream()  # Stream for the qubit state for the 2nd sequence y180-x90
    n_st = declare_stream()       # Stream for the averaging iteration 'n'

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(a, amps)):
            # Play the 1st sequence with varying DRAG coefficient: x180 then y90
            play("x180" * amp(1, 0, 0, a), qubit_key)
            play("y90" * amp(a, 0, 0, 1), qubit_key)
            # Align to measure after playing the qubit pulses
            align(qubit_key, res_key)
            # Measure the resonator and extract the qubit state
            state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
            # Wait for the qubit to decay to the ground state
            wait(thermalization_time, res_key)
            # Save the 'I', 'Q' quadratures and state to their respective streams
            save(I, I1_st)
            save(Q, Q1_st)
            save(state, state1_st)

            align()  # Global align between the two sequences

            # Play the 2nd sequence with varying DRAG coefficient: y180 then x90
            play("y180" * amp(a, 0, 0, 1), qubit_key)
            play("x90" * amp(1, 0, 0, a), qubit_key)
            # Align to measure after playing the qubit pulses
            align(qubit_key, res_key)
            # Measure the resonator and extract the qubit state
            state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
            # Wait for the qubit to decay to the ground state
            wait(thermalization_time, res_key)
            # Save the 'I', 'Q' quadratures and state to their respective streams
            save(I, I2_st)
            save(Q, Q2_st)
            save(state, state2_st)

        save(n, n_st)

    with stream_processing():
        I1_st.buffer(len(amps)).average().save("I1")
        Q1_st.buffer(len(amps)).average().save("Q1")
        I2_st.buffer(len(amps)).average().save("I2")
        Q2_st.buffer(len(amps)).average().save("Q2")
        state1_st.boolean_to_int().buffer(len(amps)).average().save("state1")
        state2_st.boolean_to_int().buffer(len(amps)).average().save("state2")
        n_st.save("iteration")

#####################################
#  Open Communication with the QOP  #
#####################################
from qm import CompilerOptionArguments
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=10_000)
    job = qmm.simulate(config, prog, simulation_config, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    samples = job.get_simulated_samples()
    samples.con1.plot()
    waveform_report = job.get_simulated_waveform_report()
    waveform_dict = waveform_report.to_dict()
    waveform_report.create_plot(samples, plot=True, save_path=str(Path(__file__).resolve()))
else:
    qm = qmm.open_qm(config, close_other_machines=True, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    job = qm.execute(prog)
    results = fetching_tool(job, data_list=["I1", "I2", "Q1", "Q2", "state1", "state2", "iteration"], mode="live")
    fig = plt.figure()
    interrupt_on_close(fig, job)

    while results.is_processing():
        I1, I2, Q1, Q2, state1, state2, iteration = results.fetch_all()
        I1, Q1 = u.demod2volts(I1, readout_len), u.demod2volts(Q1, readout_len)
        I2, Q2 = u.demod2volts(I2, readout_len), u.demod2volts(Q2, readout_len)
        progress_counter(iteration, n_avg, start_time=results.get_start_time())
        plt.suptitle(f"{qubit_key}, DRAG calibration (Yale), {iteration + 1}/{n_avg}")
        plt.subplot(311)
        plt.cla()
        plt.plot(amps * drag_coef, I1, label="x180y90")
        plt.plot(amps * drag_coef, I2, label="y180x90")
        plt.ylabel("I [V]")
        plt.legend()
        plt.subplot(312)
        plt.cla()
        plt.plot(amps * drag_coef, Q1, label="x180y90")
        plt.plot(amps * drag_coef, Q2, label="y180x90")
        plt.ylabel("Q [V]")
        plt.legend()
        plt.subplot(313)
        plt.cla()
        plt.plot(amps * drag_coef, state1, label="x180y90")
        plt.plot(amps * drag_coef, state2, label="y180x90")
        plt.xlabel("DRAG coefficient")
        plt.ylabel("g-e transition probability")
        plt.legend()
        plt.tight_layout()
        plt.pause(0.1)

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"I1_data": I1})
    save_data_dict.update({"Q1_data": Q1})
    save_data_dict.update({"I2_data": I2})
    save_data_dict.update({"Q2_data": Q2})
    save_data_dict.update({"state1_data": state1})
    save_data_dict.update({"state2_data": state2})
    save_data_dict.update({"fig_live": fig})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    qm.close()
