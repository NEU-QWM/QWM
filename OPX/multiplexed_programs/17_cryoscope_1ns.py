"""
        CRYOSCOPE with 1ns granularity (multiplexed version)

The goal of this protocol is to measure the step response of the flux line and design proper FIR and IIR filters
(implemented on the OPX) to pre-distort the flux pulses and improve the two-qubit gates fidelity.

This version sweeps the flux pulse duration using the baking tool, which means that the flux pulse can be scanned with
a 1ns resolution, but must be shorter than ~260ns. If you want to measure longer flux pulses, use the 4ns version
(17_cryoscope_4ns.py).

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit gates (x90 and y90) by running qubit spectroscopy, rabi_chevron, power_rabi, Ramsey and updated the configuration.

Next steps before going to the next node:
    - Update the FIR and IIR filter taps in the configuration.
    - WARNING: the digital filters will add a global delay --> need to recalibrate IQ blobs (rotation_angle & ge_threshold).
"""

import matplotlib.pyplot as plt
from configuration import *
from macros import ge_averaged_measurement, single_qubit_parser
from qm import QuantumMachinesManager, SimulationConfig
from qm.qua import *
from qualang_tools.bakery import baking
from qualang_tools.plot import interrupt_on_close
from qualang_tools.results import fetching_tool, progress_counter
from qualang_tools.results.data_handler import DataHandler
from scipy import optimize, signal
from configuration.OPX1000config import *


####################
# Helper functions #
####################
def exponential_decay(x, a, t):
    """Exponential decay defined as 1 + a * np.exp(-x / t)."""
    return 1 + a * np.exp(-x / t)


def exponential_correction(A, tau, Ts=1e-9):
    """Derive FIR and IIR filter taps based on the exponential coefficients A and tau."""
    tau = tau * Ts
    k1 = Ts + 2 * tau * (A + 1)
    k2 = Ts - 2 * tau * (A + 1)
    c1 = Ts + 2 * tau
    c2 = Ts - 2 * tau
    feedback_tap = k2 / k1
    feedforward_taps = np.array([c1, c2]) / k1
    return feedforward_taps, feedback_tap


def filter_calc(exponential):
    """Derive FIR and IIR filter taps based on a list of exponential coefficients."""
    b = np.zeros((2, len(exponential)))
    feedback_taps = np.zeros(len(exponential))
    for i, (A, tau) in enumerate(exponential):
        b[:, i], feedback_taps[i] = exponential_correction(A, tau)
    feedforward_taps = b[:, 0]
    for i in range(len(exponential) - 1):
        feedforward_taps = np.convolve(feedforward_taps, b[:, i + 1])
    if np.abs(max(feedforward_taps)) >= 2:
        feedforward_taps = 2 * feedforward_taps / max(feedforward_taps)
    return feedforward_taps, feedback_taps


def baked_waveform(waveform, pulse_duration, flux_element):
    """Bake flux waveform segments with 1ns resolution using the baking tool."""
    pulse_segments = []
    for i in range(0, pulse_duration + 1):
        with baking(config, padding_method="right") as b:
            if i == 0:
                wf = [0.0] * 16
            else:
                wf = waveform[:i].tolist()
            b.add_op("flux_pulse", flux_element, wf)
            b.play("flux_pulse", flux_element)
        pulse_segments.append(b)
    return pulse_segments


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
    "x180_len",
]
res_key, readout_len, qubit_relaxation, ge_threshold, flux_key, const_flux_len, const_flux_amp, x180_len = (
    single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles

n_avg = 10_000  # Number of averages
state_discrimination = False

# Flux pulse waveform generation
# The zeros are just here to visualize the rising and falling times of the flux pulse.
zeros_before_pulse = 20  # Beginning of the flux pulse (before we put zeros to see the rising time)
zeros_after_pulse = 20   # End of the flux pulse (after we put zeros to see the falling time)
total_zeros = zeros_after_pulse + zeros_before_pulse
flux_waveform = np.array([0.0] * zeros_before_pulse + [const_flux_amp] * const_flux_len + [0.0] * zeros_after_pulse)

# Baked flux pulse segments with 1ns resolution
square_pulse_segments = baked_waveform(flux_waveform, len(flux_waveform), flux_key)
step_response_th = (
    [0.0] * zeros_before_pulse + [1.0] * (const_flux_len + 1) + [0.0] * zeros_after_pulse
)  # Perfect step response (square)
xplot = np.arange(0, len(flux_waveform) + 1, 1)  # x-axis for plotting - must be in ns.

save_dir = Path(__file__).resolve().parent / "data"
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "flux_waveform": flux_waveform,
    "config": config,
}

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)
    segment = declare(int)
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
        with for_(segment, 0, segment <= const_flux_len + total_zeros, segment + 1):
            with for_each_(flag, [True, False]):
                # Play first X/2
                play("x90", qubit_key)
                # Play truncated baked flux pulse
                align(qubit_key, flux_key)
                wait(20 * u.ns)
                with switch_(segment):
                    for j in range(0, len(flux_waveform) + 1):
                        with case_(j):
                            square_pulse_segments[j].run()
                # Wait for the idle time set slightly above the maximum flux pulse duration
                wait((len(flux_waveform) + 20) * u.ns, qubit_key)
                # Play second X/2 or Y/2
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
        I_st.buffer(2).buffer(const_flux_len + total_zeros + 1).average().save("I")
        Q_st.buffer(2).buffer(const_flux_len + total_zeros + 1).average().save("Q")
        if state_discrimination:
            state_st.boolean_to_int().buffer(2).buffer(const_flux_len + total_zeros + 1).average().save("state")
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

        progress_counter(iteration, n_avg, start_time=results.get_start_time())
        qubit_phase = np.unwrap(np.angle(qubit_state))
        qubit_phase = qubit_phase - qubit_phase[-1]
        detuning = signal.savgol_filter(qubit_phase / 2 / np.pi, 13, 3, deriv=1, delta=0.001)
        step_response_freq = detuning / np.average(detuning[-int(const_flux_len / 2):])
        step_response_volt = np.sqrt(step_response_freq)
        qubit_coherence = np.abs(qubit_state)

        plt.suptitle(f"Cryoscope with 1ns resolution - {qubit_key}")
        plt.subplot(221)
        plt.cla()
        plt.plot(xplot, I)
        plt.xlabel("Pulse duration [ns]")
        plt.ylabel("I quadrature [V]")
        plt.legend(("X", "Y"), loc="lower right")

        plt.subplot(222)
        plt.cla()
        plt.plot(xplot, Q)
        plt.xlabel("Pulse duration [ns]")
        plt.ylabel("Q quadrature [V]")
        plt.legend(("X", "Y"), loc="lower right")

        plt.subplot(223)
        plt.cla()
        plt.plot(xplot, state)
        plt.xlabel("Pulse duration [ns]")
        plt.ylabel("Excited state population")
        plt.legend(("X", "Y"), loc="lower right")

        plt.subplot(224)
        plt.cla()
        plt.plot(xplot, step_response_freq, label="Frequency")
        plt.plot(xplot, step_response_volt, label=r"Voltage ($\sqrt{freq}$)")
        plt.xlabel("Pulse duration [ns]")
        plt.ylabel("Step response")
        plt.legend()
        plt.tight_layout()
        plt.pause(0.1)

    # Fit step response with exponential
    [A, tau], _ = optimize.curve_fit(exponential_decay, xplot, step_response_volt)
    print(f"A: {A}\ntau: {tau}")

    # Derive IIR and FIR corrections
    fir, iir = filter_calc(exponential=[(A, tau)])
    print(f"FIR: {fir}\nIIR: {iir}")

    # Response without filter
    no_filter = exponential_decay(xplot, A, tau)
    # Response with filters
    with_filter = no_filter * signal.lfilter(fir, [1, iir[0]], step_response_th)

    plt.rcParams.update({"font.size": 13})
    plt.figure()
    plt.suptitle(f"Cryoscope with filter implementation - {qubit_key}")
    plt.plot(xplot, step_response_volt, "o-", label="Experimental data")
    plt.plot(xplot, no_filter, label="Fitted response without filter")
    plt.plot(xplot, with_filter, label="Fitted response with filter")
    plt.plot(xplot, step_response_th, label="Ideal WF")
    plt.text(
        max(xplot) // 2,
        max(step_response_volt) / 2,
        f"IIR = {iir}\nFIR = {fir}",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )
    plt.text(
        max(xplot) // 4,
        max(step_response_volt) / 2,
        f"A = {A:.2f}\ntau = {tau:.2f}",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )
    plt.xlabel("Flux pulse duration [ns]")
    plt.ylabel("Step response")
    plt.legend(loc="upper right")
    plt.tight_layout()

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
