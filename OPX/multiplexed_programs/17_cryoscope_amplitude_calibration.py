"""
        CRYOSCOPE - AMPLITUDE CALIBRATION (multiplexed version)

The goal of this protocol is to calibrate the flux pulse amplitude by measuring the qubit frequency shift
as a function of the flux pulse amplitude (with fixed duration). This allows constructing the relationship
between the applied voltage and the resulting qubit frequency detuning, which is essential for accurate
flux pulse calibration in two-qubit gate experiments.

The sequence consists of a Ramsey sequence ("x90" - flux pulse (fixed duration, varying amplitude) - "x90" or "y90").
The Sx and Sy components of the Bloch vector are measured to extract the qubit dephasing as a function of flux amplitude.

The post-processing computes the accumulated phase as a function of flux amplitude, then fits it with a polynomial
(typically degree 2) to extract the flux-to-frequency calibration curve.

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit gates (x90 and y90) by running qubit spectroscopy, rabi_chevron, power_rabi, Ramsey and updated the configuration.
    - (optional) Having calibrated the readout to perform state discrimination (IQ_blobs).
    - Set the desired flux bias.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.plot import interrupt_on_close
from qualang_tools.loops import from_array
from macros import ge_averaged_measurement, single_qubit_parser
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
    "flux_key",
    "const_flux_len",
    "const_flux_amp",
]
res_key, readout_len, qubit_relaxation, ge_threshold, flux_key, const_flux_len, const_flux_amp = (
    single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles

n_avg = 10_000  # Number of averages
# Flag to set to True if state discrimination is calibrated
state_discrimination = False
# Flux amplitude sweep (as a pre-factor of the flux amplitude) - must be within [-2; 2)
flux_amp_array = np.linspace(0, -0.2, 101)

save_dir = Path(__file__).resolve().parent / "data"
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "flux_amp_array": flux_amp_array,
    "config": config,
}

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)
    flux_amp = declare(fixed)
    flag = declare(bool)
    I = declare(fixed)
    Q = declare(fixed)
    if state_discrimination:
        state = declare(bool)
        state_st = declare_stream()
    I_st = declare_stream()
    Q_st = declare_stream()
    n_st = declare_stream()

    if not state_discrimination:
        Ig_st, Qg_st, Ie_st, Qe_st = ge_averaged_measurement(qubit_key, res_key, thermalization_time, n_avg)

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(flux_amp, flux_amp_array)):
            with for_each_(flag, [True, False]):
                # Play first X/2
                play("x90", qubit_key)
                # Play flux pulse with varying amplitude (fixed duration)
                align(qubit_key, flux_key)
                wait(20 * u.ns)
                play("const" * amp(flux_amp), flux_key)
                align(qubit_key, flux_key)
                wait(20 * u.ns)
                # Play second X/2 or Y/2
                align(qubit_key, flux_key)
                with if_(flag):
                    play("x90", qubit_key)
                with else_():
                    play("y90", qubit_key)
                # Measure resonator state
                align(res_key, qubit_key)
                measure(
                    "readout",
                    res_key,
                    None,
                    dual_demod.full("cos", "sin", I),
                    dual_demod.full("minus_sin", "cos", Q),
                )
                if state_discrimination:
                    assign(state, I > ge_threshold)
                    save(state, state_st)
                wait(thermalization_time, res_key)
                save(I, I_st)
                save(Q, Q_st)
        save(n, n_st)

    with stream_processing():
        I_st.buffer(2).buffer(len(flux_amp_array)).average().save("I")
        Q_st.buffer(2).buffer(len(flux_amp_array)).average().save("Q")
        if state_discrimination:
            state_st.boolean_to_int().buffer(2).buffer(len(flux_amp_array)).average().save("state")
        else:
            Ig_st.average().save("Ig")
            Qg_st.average().save("Qg")
            Ie_st.average().save("Ie")
            Qe_st.average().save("Qe")
        n_st.save("iteration")

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
    qm = qmm.open_qm(config, close_other_machines=True, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    job = qm.execute(prog)
    if state_discrimination:
        results = fetching_tool(job, data_list=["I", "Q", "state", "iteration"], mode="live")
    else:
        results = fetching_tool(job, data_list=["I", "Q", "Ie", "Qe", "Ig", "Qg", "iteration"], mode="live")
    fig = plt.figure()
    interrupt_on_close(fig, job)
    xplot = flux_amp_array * const_flux_amp
    while results.is_processing():
        if state_discrimination:
            I, Q, state, iteration = results.fetch_all()
            I, Q = u.demod2volts(I, readout_len), u.demod2volts(Q, readout_len)
            qubit_state = (state[:, 0] * 2 - 1) + 1j * (state[:, 1] * 2 - 1)
        else:
            I, Q, Ie, Qe, Ig, Qg, iteration = results.fetch_all()
            phase_g = np.angle(Ig + 1j * Qg)
            phase_e = np.angle(Ie + 1j * Qe)
            phase = np.unwrap(np.angle(I + 1j * Q))
            state = (phase - phase_g) / (phase_e - phase_g)
            I, Q = u.demod2volts(I, readout_len), u.demod2volts(Q, readout_len)
            qubit_state = (state[:, 0] * 2 - 1) + 1j * (state[:, 1] * 2 - 1)

        # Accumulated phase: angle between Sx and Sy
        qubit_phase = np.unwrap(np.angle(qubit_state))
        detuning = qubit_phase / (2 * np.pi * const_flux_len / u.s)
        qubit_coherence = np.abs(qubit_state)
        # Quadratic fit of detuning versus flux pulse amplitude
        pol = np.polyfit(xplot, detuning, deg=2)

        progress_counter(iteration, n_avg, start_time=results.get_start_time())
        plt.suptitle(f"Cryoscope amplitude calibration - {qubit_key}")
        plt.subplot(221)
        plt.cla()
        plt.plot(xplot, I)
        plt.xlabel("Flux pulse amplitude [V]")
        plt.ylabel("I quadrature [V]")
        plt.legend(("X", "Y"), loc="lower right")

        plt.subplot(222)
        plt.cla()
        plt.plot(xplot, Q)
        plt.xlabel("Flux pulse amplitude [V]")
        plt.ylabel("Q quadrature [V]")
        plt.legend(("X", "Y"), loc="lower right")

        plt.subplot(223)
        plt.cla()
        plt.plot(xplot, state)
        plt.xlabel("Flux pulse amplitude [V]")
        plt.ylabel("Excited state population")
        plt.legend(("X", "Y"), loc="lower right")

        plt.subplot(224)
        plt.cla()
        plt.plot(xplot, detuning / u.MHz, "bo")
        plt.plot(xplot, np.polyval(pol, xplot) / u.MHz, "r-")
        plt.xlabel("Flux pulse amplitude [V]")
        plt.ylabel("Averaged detuning [MHz]")
        plt.legend(("data", "Fit"), loc="upper right")
        plt.tight_layout()
        plt.pause(0.1)

    qm.close()
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    if state_discrimination:
        save_data_dict.update({"I_data": I})
        save_data_dict.update({"Q_data": Q})
        save_data_dict.update({"state_data": state})
    else:
        save_data_dict.update({"I_data": I})
        save_data_dict.update({"Q_data": Q})
        save_data_dict.update({"Ig_data": Ig})
        save_data_dict.update({"Qg_data": Qg})
        save_data_dict.update({"Ie_data": Ie})
        save_data_dict.update({"Qe_data": Qe})
    save_data_dict.update({"fig_live": fig})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])
