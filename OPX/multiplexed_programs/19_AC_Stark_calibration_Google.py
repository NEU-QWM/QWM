"""
        AC STARK-SHIFT CALIBRATION WITH DRAG PULSES - GOOGLE METHOD (multiplexed version)

The sequence consists in applying an increasing number of x180 and -x180 pulses successively for different DRAG
detunings. Here the detuning sweep has to be performed in Python, because it involves changing the DRAG waveforms in a
non-linear manner. After such a sequence, the qubit is expected to always be in the ground state if the AC Stark shift
is properly compensated by the DRAG detuning.

One can then take a line cut for a given number of pulses and fit the 1D trace with a parabola to get the optimum
detuning and update its value in the configuration.

This protocol is described in more details in https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.117.190503

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit pi pulse (x180) by running qubit, spectroscopy, rabi_chevron, power_rabi and updated the config.
    - (optional) Having calibrated the readout (readout_frequency, amplitude, duration_optimization IQ_blobs) for better SNR.
    - Having calibrated the DRAG coefficient.
    - Set the desired flux bias.

Next steps before going to the next node:
    - Update the DRAG detuning (AC_stark_detuning) in the configuration.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import fetching_tool
from qualang_tools.loops import from_array
from macros import readout_macro, single_qubit_parser
import matplotlib.pyplot as plt
from qualang_tools.results.data_handler import DataHandler
from configuration.OPX1000config import *


##################
#   Parameters   #
##################
qubit_key = "q1"
required_parameters = [
    "resonator_key",
    "readout_len",
    "qubit_relaxation",
    "ge_threshold",
    "x180_amp",
    "x180_len",
    "x180_sigma",
    "drag_coef",
    "anharmonicity",
]
res_key, readout_len, qubit_relaxation, ge_threshold, x180_amp, x180_len, x180_sigma, drag_coef, anharmonicity = (
    single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles

n_avg = 100
# Detuning to compensate for the AC Stark-shift
detunings = np.arange(-10e6, 10e6, 1e6)
# Scan the number of pulses
iter_min = 0
iter_max = 25
d = 1
iters = np.arange(iter_min, iter_max + 0.1, d)

save_dir = Path(__file__).resolve().parent / "data"
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "detunings": detunings,
    "iters": iters,
    "config": config,
}

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)
    it = declare(int)
    pulses = declare(int)
    I = declare(fixed)
    Q = declare(fixed)
    state = declare(bool)
    I_st = declare_stream()
    Q_st = declare_stream()
    state_st = declare_stream()

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(it, iters)):
            with for_(pulses, iter_min, pulses <= it, pulses + d):
                play("x180" * amp(1), qubit_key)
                play("x180" * amp(-1), qubit_key)
            align(qubit_key, res_key)
            state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
            wait(thermalization_time, res_key)
            save(I, I_st)
            save(Q, Q_st)
            save(state, state_st)

    with stream_processing():
        I_st.buffer(len(iters)).average().save("I")
        Q_st.buffer(len(iters)).average().save("Q")
        state_st.boolean_to_int().buffer(len(iters)).average().save("state")

#####################################
#  Open Communication with the QOP  #
#####################################
from opx_credentials import qop_ip, cluster
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
    xaxis = []
    I_tot = []
    Q_tot = []
    state_tot = []
    fig = plt.figure()
    # Since the DRAG waveforms need to be changed, we have to do it in Python
    for det in detunings:
        xaxis.append(det)
        # Derive the DRAG waveforms with the new detuning
        x180_wf, x180_der_wf = np.array(
            drag_gaussian_pulse_waveforms(
                x180_amp, x180_len, x180_sigma, alpha=drag_coef, anharmonicity=anharmonicity, detuning=det
            )
        )
        x180_I_wf = x180_wf
        x180_Q_wf = x180_der_wf
        # Update the config waveforms for the selected qubit
        qubit_idx = int(qubit_key[1]) - 1
        config["waveforms"][f"x180_I_wf_{qubit_idx + 1}"]["samples"] = x180_I_wf.tolist()
        config["waveforms"][f"x180_Q_wf_{qubit_idx + 1}"]["samples"] = x180_Q_wf.tolist()
        # Open the quantum machine with the updated config
        qm = qmm.open_qm(config, close_other_machines=True, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
        job = qm.execute(prog)
        results = fetching_tool(job, data_list=["I", "Q", "state"])
        I, Q, state = results.fetch_all()
        I, Q = u.demod2volts(I, readout_len), u.demod2volts(Q, readout_len)
        I_tot.append(I)
        Q_tot.append(Q)
        state_tot.append(state)

        plt.suptitle(f"AC stark shift calibration - {qubit_key}")
        plt.subplot(231)
        plt.cla()
        plt.pcolor(iters, xaxis, I_tot)
        plt.xlabel("# of x180-x180 pulses")
        plt.ylabel("Detuning [Hz]")
        plt.title("I [V]")
        plt.subplot(232)
        plt.cla()
        plt.pcolor(iters, xaxis, Q_tot)
        plt.xlabel("# of x180-x180 pulses")
        plt.ylabel("Detuning [Hz]")
        plt.title("Q [V]")
        plt.subplot(233)
        plt.cla()
        plt.pcolor(iters, xaxis, state_tot)
        plt.xlabel("# of x180-x180 pulses")
        plt.ylabel("Detuning [Hz]")
        plt.title("state")
        plt.subplot(212)
        plt.cla()
        plt.plot(xaxis, np.sum(I_tot, axis=1))
        plt.xlabel("DRAG detuning [Hz]")
        plt.ylabel("Sum along the iterations")
        plt.tight_layout()
        plt.pause(0.01)
    print(f"Optimal DRAG detuning = {xaxis[np.argmin(np.sum(I_tot, axis=1))]:.0f} Hz")

    qm.close()
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"I_data": I})
    save_data_dict.update({"Q_data": Q})
    save_data_dict.update({"state_data": state})
    save_data_dict.update({"fig_live": fig})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])
