"""
        RESONATOR SPECTROSCOPY VERSUS FLUX
This sequence involves measuring the resonator by sending a readout pulse and demodulating the signals to
extract the 'I' and 'Q' quadratures across various readout intermediate frequencies and flux biases.
The resonator frequency as a function of flux bias is then extracted and fitted so that the parameters
can be stored in the configuration.

This information can then be used to adjust the readout frequency for the maximum frequency point.

Prerequisites:
    - Calibration of the time of flight, offsets, and gains (referenced as "time_of_flight").
    - Identification of the resonator's resonance frequency (referred to as "resonator_spectroscopy").
    - Configuration of the readout pulse amplitude and duration.
    - Specification of the expected resonator depletion time in the configuration.

Before proceeding to the next node:
    - Update the readout frequency, labeled as "resonator_IF", in the configuration.
    - Adjust the flux bias to the maximum frequency point ("max_frequency_point") in the configuration.
    - Update the resonator frequency versus flux fit parameters
      (amplitude_fit, frequency_fit, phase_fit, offset_fit) in the configuration.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.plot import interrupt_on_close
from qualang_tools.loops import from_array
import matplotlib.pyplot as plt
from scipy import signal
from scipy.optimize import curve_fit
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
qubit_key = "q1"
required_parameters = [
    "resonator_key", "resonator_IF", "resonator_frequency", "readout_len", "resonator_relaxation",
    "flux_key", "flux_settle_time",
]
res_key, res_IF, res_frequency, readout_len, res_relaxation, flux_key, flux_settle_time = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

depletion_time = res_relaxation // 4  # ns → clock cycles
flux_settle_clk = flux_settle_time // 4  # ns → clock cycles

n_avg = 6000  # Number of averaging loops
# Frequency sweep around the resonator IF
span = 10 * u.MHz
df = 100 * u.kHz
dfs = np.arange(-span, +span + 0.1, df)
# Flux bias sweep in V
flux_min = -0.49
flux_max = 0.49
flux_step = 0.01
flux = np.arange(flux_min, flux_max + flux_step / 2, flux_step)

# ---- Data to save ---- #
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "dfs": dfs,
    "flux": flux,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)       # averaging loop
    f = declare(int)       # readout IF sweep
    dc = declare(fixed)    # flux bias
    I = declare(fixed)
    Q = declare(fixed)
    I_st = declare_stream()
    Q_st = declare_stream()
    n_st = declare_stream()

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(f, dfs)):
            update_frequency(res_key, f + res_IF)
            with for_(*from_array(dc, flux)):
                # Set the flux bias via DC offset on the flux line
                set_dc_offset(flux_key, "single", dc)
                wait(flux_settle_clk, res_key, flux_key)
                measure(
                    "readout",
                    res_key,
                    dual_demod.full("cos", "sin", I),
                    dual_demod.full("minus_sin", "cos", Q),
                )
                wait(depletion_time, res_key)
                save(I, I_st)
                save(Q, Q_st)
        save(n, n_st)

    with stream_processing():
        I_st.buffer(len(flux)).buffer(len(dfs)).average().save("I")
        Q_st.buffer(len(flux)).buffer(len(dfs)).average().save("Q")
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
    results = fetching_tool(job, data_list=["I", "Q", "iteration"], mode="live")
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, sharey=True)
    interrupt_on_close(fig, job)
    try:
        while results.is_processing():
            I, Q, iteration = results.fetch_all()
            progress_counter(iteration, n_avg, start_time=results.get_start_time())
            S = u.demod2volts(I + 1j * Q, readout_len)
            R = np.abs(S)
            phase = np.angle(S)
            fig.suptitle(f"Resonator {res_key} spectroscopy vs flux, {iteration + 1}/{n_avg}")
            ax1.cla()
            ax2.cla()
            ax1.pcolor(flux, (dfs + res_frequency) / u.GHz, R, cmap="magma")
            ax1.set_ylabel("Readout frequency (GHz)")
            ax1.set_title(r"$R=\sqrt{I^2 + Q^2}$ (V)")
            ax2.pcolor(flux, (dfs + res_frequency) / u.GHz, signal.detrend(np.unwrap(phase, axis=0)), cmap="RdBu")
            ax2.set_xlabel("Flux bias (V)")
            ax2.set_ylabel("Readout frequency (GHz)")
            ax2.set_title("Phase (rad)")
            fig.tight_layout()
            fig.canvas.draw_idle()
            plt.pause(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user.")

    # Fit the resonator frequency vs flux
    def cosine_func(x, amplitude, frequency, phase, offset):
        return amplitude * np.cos(2 * np.pi * frequency * x + phase) + offset

    try:
        # Find resonator frequency at each flux point (minimum of R)
        freq_vs_flux = (dfs + res_frequency)[np.argmin(R, axis=0)]
        popt, _ = curve_fit(cosine_func, flux, freq_vs_flux, p0=[1e6, 1, 0, res_frequency], maxfev=5000)
        print(f"Fit results for {res_key} vs flux:")
        print(f"  amplitude_fit = {popt[0]:.0f} Hz")
        print(f"  frequency_fit = {popt[1]:.3f} /V")
        print(f"  phase_fit     = {popt[2]:.3f} rad")
        print(f"  offset_fit    = {popt[3]:.0f} Hz")
        fig_fit, ax = plt.subplots()
        ax.plot(flux, freq_vs_flux / u.GHz, ".", label="Data")
        ax.plot(flux, cosine_func(flux, *popt) / u.GHz, label="Fit")
        ax.set_xlabel("Flux bias (V)")
        ax.set_ylabel("Resonator frequency (GHz)")
        ax.set_title(f"Resonator {res_key} frequency vs flux")
        ax.legend()
    except Exception as e:
        print(f"Fit failed: {e}")

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"I_data": I, "Q_data": Q})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    qm.close()
