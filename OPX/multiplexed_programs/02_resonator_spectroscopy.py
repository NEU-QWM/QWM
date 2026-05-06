"""
        RESONATOR SPECTROSCOPY
This sequence involves measuring the resonator by sending a readout pulse and demodulating the signals to extract the
'I' and 'Q' quadratures across varying readout intermediate frequencies.
The data is then post-processed to determine the resonator resonance frequency.
This frequency can be used to update the readout intermediate frequency in the configuration under "resonator_IF".

Prerequisites:
    - Ensure calibration of the time of flight, offsets, and gains (referenced as "time_of_flight").
    - Calibrate the IQ mixer connected to the readout line (whether it's an external mixer or an Octave port).
    - Define the readout pulse amplitude and duration in the configuration.
    - Specify the expected resonator depletion time in the configuration.

Before proceeding to the next node:
    - Update the readout frequency, labeled as "resonator_IF", in the configuration.
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
# Parameters Definition
n_avg = 5000  # Number of averaging loops
qubit_key = "q1"
required_parameters = ["resonator_key", "resonator_relaxation", "resonator_frequency", "resonator_IF", "readout_len", "readout_amp"]
res_key, res_relaxation, res_frequency, res_IF, readout_len, readout_amp = single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)

depletion_time = res_relaxation//4 # From ns to clock cycles

res_frequency = res_frequency
res_spec_span = 8 * u.MHz
res_spec_df = 10 * u.kHz
res_spec_sweep_dfs = np.arange(-res_spec_span//2, res_spec_span//2 + res_spec_df, res_spec_df)
res_spec_frequency = res_spec_sweep_dfs + res_frequency

# ---- Data to save ---- #
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "frequency": res_spec_frequency,
    "config": config,
    "readout_amp":readout_amp,
}
save_dir = Path(__file__).resolve().parent / "data"

# ---- Resonator spectroscopy QUA program ---- #
with program() as prog:
    reset_global_phase()
    n = declare(int) # QUA variable for the averaging loop
    df = declare(int) # QUA variable for the sweep of the readout IF frequency
    I = declare(fixed) # QUA variable for the measured 'I' quadrature
    Q = declare(fixed) # QUA variable for the measured 'Q' quadrature
    I_st = declare_stream() # Stream for the 'I' quadrature
    Q_st = declare_stream() # Stream for the 'Q' quadrature
    n_st = declare_stream() # Stream for the averaging counter

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(df, res_spec_sweep_dfs)):
            update_frequency(res_key, df + res_IF) # Update the frequency of the digital oscillator linked to the resonator element
            measure(
                "readout",
                res_key,
                dual_demod.full("cos", "sin", I),
                dual_demod.full("minus_sin", "cos", Q),
            )
            # Save the 'I' & 'Q' quadratures to their respective streams
            save(I, I_st)
            save(Q, Q_st)
            # Wait for the resonator to deplete
            wait(depletion_time, res_key)
        save(n, n_st)
    with stream_processing():
        n_st.save("iteration")
        I_st.buffer(len(res_spec_sweep_dfs)).average().save("I")
        Q_st.buffer(len(res_spec_sweep_dfs)).average().save("Q")

# ---- Open communication with the OPX ---- #
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    # Simulates the QUA program for the specified duration
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
    # Open the quantum machine
    qm = qmm.open_qm(config, close_other_machines=True)
    # Send the QUA program to the OPX, which compiles and executes it
    job = qm.execute(prog)
    # Creates a result handle to fetch data from the OPX
    res_handles = fetching_tool(job, data_list = ["iteration", "I", "Q"], mode = "live")
    # Waits (blocks the Python console) until all results have been acquired
    IQ = False
    fig_live, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
    interrupt_on_close(fig_live, job)  # Interrupts the job when closing the figure
    try:
        while res_handles.is_processing():
            # Fetch results
            iteration, I, Q = res_handles.fetch_all()
            # Convert results into Volts
            I = u.demod2volts(I, readout_len)
            Q = u.demod2volts(Q, readout_len)
            S = I + 1j * Q
            R = np.abs(S)  # Amplitude
            phase = np.angle(S)  # Phase
            # Progress bar
            progress_counter(iteration, n_avg, start_time=res_handles.get_start_time())
            # Plot results (update axes)
            fig_live.suptitle(f"Resonator {res_key} spectroscopy, iteration {iteration+1}/{n_avg}, amp {readout_amp}")
            ax1.cla()
            ax2.cla()
            if IQ:
                ax1.plot((res_spec_sweep_dfs) / u.MHz, I, label=f"Resonator {res_key} at {res_frequency/u.MHz:.3f} MHz")
                ax1.set_ylabel("I (V)")

                ax2.plot((res_spec_sweep_dfs) / u.MHz, Q, label=f"Resonator {res_key} at {res_frequency/u.MHz:.3f} MHz")
                ax2.set_ylabel("Q (V)")
            else:
                ax1.plot((res_spec_sweep_dfs) / u.MHz, R, label=f"Resonator {res_key} at {res_frequency/u.MHz:.3f} MHz")
                ax1.set_ylabel(r"$R=\sqrt{I^2 + Q^2}$ (V)")

                ax2.plot((res_spec_sweep_dfs) / u.MHz, signal.detrend(np.unwrap(phase)), label=f"Resonator {res_key} at {res_frequency/u.MHz:.3f} MHz")
                ax2.set_ylabel("Phase (rad)")
                
            ax2.set_xlabel(r"$\Delta f$ (MHz)")
            
            fig_live.tight_layout()
            fig_live.canvas.draw_idle()
            plt.pause(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user.")

    # Keep the interactive plot open after acquisition until the user closes it
    message = "Acquisition finished. Close the plot window to continue."
    print(message)
    try:
        # Add a centered text box on the figure (figure coordinates)
        fig_live.text(0.04, 0.02, message, ha='left', va='bottom', fontsize=8,
                      bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        fig_live.canvas.draw_idle()  
    except Exception as e:
        print(e)
    while plt.fignum_exists(fig_live.number):
        plt.pause(0.2)

    from qualang_tools.plot.fitting import Fit

    try:
        # Fit the data
        fit = Fit()
        res_spec_fit = fit.reflection_resonator_spectroscopy((res_spec_frequency) / u.MHz, R, plot=False)
        fig = plt.figure()
        plt.plot((res_spec_frequency) / u.MHz, R, label="Data")
        x_fit = np.linspace(res_spec_frequency[0], res_spec_frequency[-1], 200) / u.MHz
        y_fit = res_spec_fit['fit_func'](x_fit)
        plt.plot(x_fit, y_fit, label="Fit")
        plt.title(f"Resonator {res_key}, Resonator spectroscopy, amp {readout_amp}")
        plt.xlabel("Frequency (MHz)")
        plt.ylabel(r"R=$\sqrt{I^2 + Q^2}$ (V))")
        print(f"Update resonator {res_key} to {res_spec_fit['f'][0]:.6f} MHz")
        msg = f"Update {res_key} → {res_spec_fit['f'][0]:.6f} MHz"
        fig.text(0.5, 0.98, msg, ha='center', va='top', fontsize=10,
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    except Exception as e:
        print(e)
        print("Unable to fit resonator " + str(res_key))
        fig = plt.figure()
        plt.plot((res_spec_frequency) / u.MHz, R)
        plt.title(f"Resonator {res_key}, Resonator spectroscopy, amp {readout_amp}")
        plt.xlabel("Frequency (MHz)")
        plt.ylabel(r"R=$\sqrt{I^2 + Q^2}$ (V)")
        msg = "Unable to fit resonator"
        fig.text(0.5, 0.98, msg, ha='center', va='top', fontsize=10,
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"I_data": I})
    save_data_dict.update({"Q_data": Q})
    save_data_dict.update({"fig_live": fig_live})
    save_data_dict.update({f"fig_fit": fig})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    # Keep the fit figures open until the user closes them
    print("Fit figures created. Close the fit figure windows to continue.")
    while plt.fignum_exists(fig.number):
        plt.pause(0.2)

    qm.close()


