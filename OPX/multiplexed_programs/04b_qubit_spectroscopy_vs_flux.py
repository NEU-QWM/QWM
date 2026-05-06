"""
        QUBIT SPECTROSCOPY VERSUS FLUX
This sequence involves doing a qubit spectroscopy for several flux biases in order to exhibit the qubit frequency
versus flux response.

Prerequisites:
    - Identification of the resonator's resonance frequency when coupled to the qubit (resonator_spectroscopy).
    - Having calibrated the resonator frequency versus flux fit parameters
      (amplitude_fit, frequency_fit, phase_fit, offset_fit) in the configuration.
    - Identification of the approximate qubit frequency (qubit_spectroscopy).

Before proceeding to the next node:
    - Update the qubit frequency, labeled as "qubit_IF", in the configuration.
    - Update the relevant flux points in the configuration.
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
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
qubit_key = "q1"
required_parameters = [
    "resonator_key", "resonator_IF", "resonator_frequency", "readout_len",
    "qubit_IF", "qubit_frequency", "qubit_relaxation",
    "flux_key", "flux_settle_time",
    "amplitude_fit", "frequency_fit", "phase_fit", "offset_fit",
]
(res_key, res_IF, res_frequency, readout_len,
 qubit_IF, qubit_frequency, qubit_relaxation,
 flux_key, flux_settle_time,
 amplitude_fit, frequency_fit, phase_fit, offset_fit) = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles
flux_settle_clk = flux_settle_time // 4  # ns → clock cycles

n_avg = 100  # Number of averaging loops
# Qubit frequency sweep around the qubit IF
spec_span = 10 * u.MHz
spec_df = 100 * u.kHz
spec_dfs = np.arange(-spec_span, +spec_span + 0.1, spec_df)
# Flux bias sweep in V
flux_min = -0.49
flux_max = 0.49
flux_step = 0.01
flux = np.arange(flux_min, flux_max + flux_step / 2, flux_step)

# Resonator frequency vs flux from the previous calibration
def cosine_func(x, amplitude, frequency, phase, offset):
    return amplitude * np.cos(2 * np.pi * frequency * x + phase) + offset

# Pre-compute the resonator IF correction at each flux point (integer Hz)
fitted_res_IF = cosine_func(flux, amplitude_fit, frequency_fit, phase_fit, offset_fit) - res_frequency + res_IF
fitted_res_IF = fitted_res_IF.astype(int)

# ---- Data to save ---- #
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "spec_dfs": spec_dfs,
    "flux": flux,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)
    f = declare(int)       # qubit IF sweep
    dc = declare(fixed)    # flux bias
    index = declare(int)   # index into resonator freq table
    I = declare(fixed)
    Q = declare(fixed)
    # Resonator IF values at each flux bias (integer LUT)
    resonator_freq = declare(int, value=fitted_res_IF.tolist())
    I_st = declare_stream()
    Q_st = declare_stream()
    n_st = declare_stream()

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(f, spec_dfs)):
            update_frequency(qubit_key, f + qubit_IF)
            assign(index, 0)
            with for_(*from_array(dc, flux)):
                # Track resonator frequency vs flux
                update_frequency(res_key, resonator_freq[index] + res_IF)
                # Set flux bias
                set_dc_offset(flux_key, "single", dc)
                wait(flux_settle_clk, res_key, qubit_key, flux_key)
                # Drive the qubit into a mixed state
                play("saturation", qubit_key)
                align(qubit_key, res_key)
                measure(
                    "readout",
                    res_key,
                    dual_demod.full("cos", "sin", I),
                    dual_demod.full("minus_sin", "cos", Q),
                )
                wait(thermalization_time, res_key)
                assign(index, index + 1)
                save(I, I_st)
                save(Q, Q_st)
        save(n, n_st)

    with stream_processing():
        I_st.buffer(len(flux)).buffer(len(spec_dfs)).average().save("I")
        Q_st.buffer(len(flux)).buffer(len(spec_dfs)).average().save("Q")
        n_st.save("iteration")

#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=10_000)
    job = qmm.simulate(config, prog, simulation_config)
    samples = job.get_simulated_samples()
    samples.con1.plot()
    waveform_report = job.get_simulated_waveform_report()
    waveform_dict = waveform_report.to_dict()
    waveform_report.create_plot(samples, plot=True, save_path=str(Path(__file__).resolve()))
else:
    qm = qmm.open_qm(config, close_other_machines=True)
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
            fig.suptitle(f"Qubit {qubit_key} spectroscopy vs flux, {iteration + 1}/{n_avg}")
            ax1.cla()
            ax2.cla()
            ax1.pcolor(flux, (spec_dfs + qubit_frequency) / u.GHz, R, cmap="magma")
            ax1.set_ylabel("Qubit frequency (GHz)")
            ax1.set_title(r"$R=\sqrt{I^2 + Q^2}$ (V)")
            ax2.pcolor(flux, (spec_dfs + qubit_frequency) / u.GHz, signal.detrend(np.unwrap(phase, axis=0)), cmap="RdBu")
            ax2.set_xlabel("Flux bias (V)")
            ax2.set_ylabel("Qubit frequency (GHz)")
            ax2.set_title("Phase (rad)")
            fig.tight_layout()
            fig.canvas.draw_idle()
            plt.pause(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user.")

    # Keep plot open
    message = "Acquisition finished. Close the plot window to continue."
    print(message)
    while plt.fignum_exists(fig.number):
        plt.pause(0.2)

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"I_data": I, "Q_data": Q})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    qm.close()
