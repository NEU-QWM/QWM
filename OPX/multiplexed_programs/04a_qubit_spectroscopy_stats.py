"""
        QUBIT SPECTROSCOPY — REPEATED ACQUISITION
This sequence repeats the standard qubit spectroscopy measurement `n_reps` times.
Each repetition sends a pulse to the qubit (placing it in a mixed/excited state) and measures the
resonator state across the swept qubit drive intermediate frequencies, averaging over `n_avg` shots.

The full spectrum of every repetition is recorded, which is useful for monitoring qubit-frequency
stability / drift over time, estimating shot-to-shot scatter, or post-selecting the best traces.

The live plot is kept and shows the current repetition (and the averaging progress within it) in the
title. After acquisition the script builds a 2D map (repetition vs. frequency), fits the mean spectrum,
and saves all repetitions to disk.

Prerequisites:
    - Identification of the resonator's resonance frequency when coupled to the qubit ("resonator_spectroscopy").
    - Calibration of the IQ mixer connected to the qubit drive line (external mixer or Octave port).
    - Configuration of the saturation pulse amplitude and duration to bring the qubit into a mixed state.
    - Specification of the expected qubit T1 in the configuration.

Before proceeding to the next node:
    - Update the qubit frequency, labeled as "qubit_IF", in the configuration.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from qm.exceptions import DataFetchingError
from configuration import *
from qualang_tools.results import progress_counter, fetching_tool
from qualang_tools.plot import interrupt_on_close
from qualang_tools.loops import from_array
import matplotlib.pyplot as plt
from scipy import signal
import time
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
# Parameters Definition
n_reps = 500  # Number of times the full qubit spectrum is measured and recorded
n_avg = 250  # Number of averaging loops per repetition
res_key = "r1"
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_frequency", "qubit_IF", "qubit_relaxation"]
res_key, readout_len, qubit_frequency, qubit_IF, qubit_relaxation = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

# thermalization_time = qubit_relaxation//4 # From ns to clock cycles
thermalization_time = 10.0 * u.us // 4  # From ns to clock cycles

print(f"Qubit frequency is {qubit_IF}")

spec_span = 100 * u.MHz
spec_df = 20 * u.kHz
spec_sweep_dfs = np.arange(-spec_span // 2, spec_span // 2 + spec_df, spec_df)
spec_frequency = spec_sweep_dfs + qubit_frequency
n_freqs = len(spec_sweep_dfs)

IQ = False  # If True, live-plot I and Q; if False, live-plot amplitude R and phase

# ---- Data to save ---- #
save_data_dict = {
    "qubit_key": qubit_key,
    "n_reps": n_reps,
    "n_avg": n_avg,
    "frequency": spec_frequency,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
# One execution of this program == one full spectrum (n_avg averaged). The repetition loop lives in
# Python so the original live-fetching behaviour is preserved and each repetition can be stored
# independently.
with program() as prog:
    reset_global_phase()
    n = declare(int)  # QUA variable for the averaging loop
    df = declare(int)  # QUA variable for the qubit frequency
    I = declare(fixed)  # QUA variable for the measured 'I' quadrature
    Q = declare(fixed)  # QUA variable for the measured 'Q' quadrature
    I_st = declare_stream()  # Stream for the 'I' quadrature
    Q_st = declare_stream()  # Stream for the 'Q' quadrature
    n_st = declare_stream()  # Stream for the averaging iteration 'n'

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(df, spec_sweep_dfs)):
            # Update the frequency of the digital oscillator linked to the qubit element
            update_frequency(qubit_key, df + qubit_IF)
            # Play the saturation pulse to put the qubit in a mixed state - Can adjust the amplitude on the fly [-2; 2)
            # play("saturation", qubit_key)
            play("x180", qubit_key)
            # Align the two elements to measure after playing the qubit pulse.
            # One can also measure the resonator while driving the qubit by commenting the 'align'
            align(qubit_key, res_key)
            # Measure the state of the resonator
            measure(
                "readout",
                res_key,
                dual_demod.full("cos", "sin", I),
                dual_demod.full("minus_sin", "cos", Q),
            )
            # Wait for the qubit to decay to the ground state
            wait(thermalization_time, res_key)
            # Save the 'I' & 'Q' quadratures to their respective streams
            save(I, I_st)
            save(Q, Q_st)
        # Save the averaging iteration to get the progress bar
        save(n, n_st)

    with stream_processing():
        # Cast the data into a 1D vector, average the 1D vectors together and store the results on the OPX processor
        n_st.save("iteration")
        I_st.buffer(len(spec_sweep_dfs)).average().save("I")
        Q_st.buffer(len(spec_sweep_dfs)).average().save("Q")


#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    # Simulates the QUA program for the specified duration (single spectrum)
    simulation_config = SimulationConfig(duration=2_000)  # In clock cycles = 4ns
    # Simulate blocks python until the simulation is done
    job = qmm.simulate(config, prog, simulation_config)
    # Get the simulated samples
    samples = job.get_simulated_samples()
    # Plot the simulated samples
    samples.con1.plot()
    # Get the waveform report object
    waveform_report = job.get_simulated_waveform_report()
    # Cast the waveform report to a python dictionary
    waveform_dict = waveform_report.to_dict()
    # Visualize and save the waveform report
    waveform_report.create_plot(samples, plot=True, save_path=str(Path(__file__).resolve()))
else:
    # Open the quantum machine once and reuse it for every repetition
    qm = qmm.open_qm(config, close_other_machines=True)

    # ---- Pre-allocate storage for every repetition ----
    I_all = np.full((n_reps, n_freqs), np.nan)
    Q_all = np.full((n_reps, n_freqs), np.nan)
    R_all = np.full((n_reps, n_freqs), np.nan)
    phase_all = np.full((n_reps, n_freqs), np.nan)
    rep_timestamps = np.full(n_reps, np.nan)  # Seconds since the start of the run (for drift studies)

    # ---- Live figure (created once, reused across repetitions) ----
    fig_live, (ax1, ax2) = plt.subplots(2, 1, sharex=True)

    t_start = time.time()
    last_completed_rep = -1
    try:
        for rep in range(n_reps):
            # Stop cleanly if the user closed the live window between repetitions
            if not plt.fignum_exists(fig_live.number):
                print("Live window closed — stopping acquisition.")
                break

            # Execute one full spectrum acquisition (n_avg averaged)
            job = qm.execute(prog)
            interrupt_on_close(fig_live, job)  # Closing the figure interrupts the current repetition
            res_handles = fetching_tool(job, data_list=["iteration", "I", "Q"], mode="live")

            # Initialise so the final-store below is always defined even if the loop body runs zero times
            I = np.full(n_freqs, np.nan)
            Q = np.full(n_freqs, np.nan)
            R = np.full(n_freqs, np.nan)
            phase = np.full(n_freqs, np.nan)

            while res_handles.is_processing():
                # Fetch results
                iteration, I, Q = res_handles.fetch_all()
        
                # Convert results into Volts
                I = u.demod2volts(I, readout_len)
                Q = u.demod2volts(Q, readout_len)
                S = I + 1j * Q
                R = np.abs(S)  # Amplitude
                phase = np.angle(S)  # Phase
                # Progress bar (per-repetition averaging progress)
                progress_counter(iteration, n_avg, start_time=res_handles.get_start_time())
                # Plot results (update axes) — repetition tracker in the title
                fig_live.suptitle(
                    f"Qubit {qubit_key} spectroscopy — repetition {rep + 1}/{n_reps} "
                    f"(averaging {iteration + 1}/{n_avg})"
                )
                ax1.cla()
                ax2.cla()
                if IQ:
                    ax1.plot(spec_sweep_dfs / u.MHz, I, label=f"Qubit {qubit_key} at {qubit_frequency/u.MHz:.3f} MHz")
                    ax1.set_ylabel("I (V)")

                    ax2.plot(spec_sweep_dfs / u.MHz, Q, label=f"Qubit {qubit_key} at {qubit_frequency/u.MHz:.3f} MHz")
                    ax2.set_ylabel("Q (V)")
                else:
                    ax1.plot(spec_sweep_dfs / u.MHz, R, label=f"Qubit {qubit_key} at {qubit_frequency/u.MHz:.3f} MHz")
                    ax1.set_ylabel(r"$R=\sqrt{I^2 + Q^2}$ (V)")

                    ax2.plot(
                        spec_sweep_dfs / u.MHz,
                        signal.detrend(np.unwrap(phase)),
                        label=f"Qubit {qubit_key} at {qubit_frequency/u.MHz:.3f} MHz",
                    )
                    ax2.set_ylabel("Phase (rad)")

                ax2.set_xlabel(r"$\Delta f$ (MHz)")
                fig_live.tight_layout()
                fig_live.canvas.draw_idle()
                plt.pause(0.1)

            # ---- Store the fully-averaged result of this repetition ----
            I_all[rep] = I
            Q_all[rep] = Q
            R_all[rep] = R
            phase_all[rep] = phase
            rep_timestamps[rep] = time.time() - t_start
            last_completed_rep = rep
            print(f"Completed repetition {rep + 1}/{n_reps}")
    except KeyboardInterrupt:
        print("Interrupted by user.")

    completed = last_completed_rep + 1
    print(f"Acquired {completed}/{n_reps} repetitions.")

    # Trim arrays to the repetitions that actually completed
    I_all = I_all[:completed]
    Q_all = Q_all[:completed]
    R_all = R_all[:completed]
    phase_all = phase_all[:completed]
    rep_timestamps = rep_timestamps[:completed]

    # ---- 2D summary map: repetition vs. frequency ----
    fig_map = None
    if completed > 0:
        fig_map, ax_map = plt.subplots()
        im = ax_map.imshow(
            R_all,
            aspect="auto",
            origin="lower",
            extent=[spec_sweep_dfs[0] / u.MHz, spec_sweep_dfs[-1] / u.MHz, 0.5, completed + 0.5],
        )
        ax_map.set_xlabel(r"$\Delta f$ (MHz)")
        ax_map.set_ylabel("Repetition")
        ax_map.set_title(f"Qubit {qubit_key} spectroscopy — {completed} repetitions")
        fig_map.colorbar(im, ax=ax_map, label=r"$R=\sqrt{I^2 + Q^2}$ (V)")
        fig_map.tight_layout()

    # ---- Fit the mean spectrum over all completed repetitions ----
    from qualang_tools.plot.fitting import Fit

    fig_fit = plt.figure()
    if completed > 0:
        R_mean = np.nanmean(R_all, axis=0)
        try:
            fit = Fit()
            spec_fit = fit.transmission_resonator_spectroscopy(spec_frequency / u.MHz, R_mean, plot=False)
            plt.plot(spec_frequency / u.MHz, R_mean, label="Mean data")
            x_fit = np.linspace(spec_frequency[0], spec_frequency[-1], 200) / u.MHz
            y_fit = spec_fit["fit_func"](x_fit)
            plt.plot(x_fit, y_fit, label="Fit")
            plt.legend()
            plt.title(f"Qubit {qubit_key} spectroscopy (mean of {completed} reps)")
            plt.xlabel("Frequency (MHz)")
            plt.ylabel(r"R=$\sqrt{I^2 + Q^2}$ (V)")
            print(f"Update Qubit {qubit_key} to {spec_fit['f'][0]:.6f} MHz")
            msg = f"Update {qubit_key} → {spec_fit['f'][0]:.6f} MHz"
            fig_fit.text(
                0.5, 0.98, msg, ha="center", va="top", fontsize=10,
                bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"),
            )
        except Exception as e:
            print(e)
            print("Unable to fit qubit " + str(qubit_key))
            plt.plot(spec_frequency / u.MHz, R_mean)
            plt.title(f"Qubit {qubit_key} spectroscopy (mean of {completed} reps)")
            plt.xlabel("Frequency (MHz)")
            plt.ylabel(r"R=$\sqrt{I^2 + Q^2}$ (V)")
            msg = "Unable to fit qubit"
            fig_fit.text(
                0.5, 0.98, msg, ha="center", va="top", fontsize=10,
                bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"),
            )
    else:
        print("No repetitions completed — nothing to fit.")

    # ---- Save results ----
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"completed_reps": completed})
    save_data_dict.update({"I_data": I_all})
    save_data_dict.update({"Q_data": Q_all})
    save_data_dict.update({"R_data": R_all})
    save_data_dict.update({"phase_data": phase_all})
    save_data_dict.update({"rep_timestamps": rep_timestamps})
    save_data_dict.update({"fig_live": fig_live})
    if fig_map is not None:
        save_data_dict.update({"fig_map": fig_map})
    save_data_dict.update({"fig_fit": fig_fit})

    # del save_data_dict["config"]

    def iterate_nested(d, current_path=""):
        for key, value in d.items():
            new_path = f"{current_path}.{key}" if current_path else key
            if isinstance(value, dict):
                iterate_nested(value, new_path)
            elif isinstance(value, np.int64):
                print(f"{new_path}: {value}, type: {type(value)}")
            else:
                pass

    iterate_nested(config)

    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    # Keep the figures open until the user closes them
    print("Acquisition finished. Close the figure windows to continue.")
    open_figs = [f for f in [fig_live, fig_map, fig_fit] if f is not None]
    while any(plt.fignum_exists(f.number) for f in open_figs):
        plt.pause(0.2)

    qm.close()