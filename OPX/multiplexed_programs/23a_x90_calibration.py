"""
        QUBIT SPECTROSCOPY VERSUS AMPLITUDE
This sequence involves sending a saturation pulse to the qubit, placing it in a mixed state,
and then measuring the state of the resonator across various qubit drive intermediate dfs.
In order to facilitate the qubit search, the qubit pulse duration and amplitude can be changed manually in the QUA
program directly without having to modify the configuration.

The data is post-processed to determine the qubit resonance frequency, which can then be used to adjust
the qubit intermediate frequency in the configuration under "qubit_IF".

Note that it can happen that the qubit is excited by the image sideband or LO leakage instead of the desired sideband.
This is why calibrating the qubit mixer is highly recommended.

This step can be repeated using the "x180" operation instead of "saturation" to adjust the pulse parameters (amplitude,
duration, frequency) before performing the next calibration steps.

Prerequisites:
    - Identification of the resonator's resonance frequency when coupled to the qubit in question (referred to as "resonator_spectroscopy").
    - Calibration of the IQ mixer connected to the qubit drive line (whether it's an external mixer or an Octave port).
    - Configuration of the saturation pulse amplitude and duration to transition the qubit into a mixed state.
    - Specification of the expected qubit T1 in the configuration.

Before proceeding to the next node:
    - Update the qubit frequency, labeled as "qubit_IF", in the configuration.
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
n_avg = 20000  # Number of averaging loops
res_key = "r1"
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_frequency", "qubit_IF", "qubit_relaxation", "control_amp"]
(res_key, readout_len, qubit_frequency, qubit_IF, qubit_relaxation, control_amp) = single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)

# thermalization_time = qubit_relaxation//4 # From ns to clock cycles
thermalization_time = 4.0 * u.us //4 # From ns to clock cycles

print(f"Qubit frequency is {qubit_IF}")

spec_span = 100 * u.MHz
spec_df = 200 * u.kHz
spec_sweep_dfs = np.arange(-spec_span//2, spec_span//2 + spec_df, spec_df)
spec_frequency = spec_sweep_dfs + qubit_frequency

# Pulse amplitude sweep (as a pre-factor of the qubit pulse amplitude) - must be within [-2; 2)
a_min = 0.04
a_max = 1.96
d_a = 0.02
amplitudes = np.arange(a_min, a_max+d_a, d_a)
# amplitudes = np.logspace(-4, 0, 50, endpoint=True)

# ---- Data to save ---- #
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "amplitude": amplitudes,
    "frequency": spec_frequency,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)  # QUA variable for the averaging loop
    df = declare(int)  # QUA variable for the qubit frequency
    a = declare(fixed)  # QUA variable for the readout amplitude pre-factor
    I = declare(fixed)  # QUA variable for the measured 'I' quadrature
    Q = declare(fixed)  # QUA variable for the measured 'Q' quadrature
    I_st = declare_stream()  # Stream for the 'I' quadrature
    Q_st = declare_stream()  # Stream for the 'Q' quadrature
    n_st = declare_stream()  # Stream for the averaging iteration 'n'

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(df, spec_sweep_dfs)):
            # Update the frequency of the digital oscillator linked to the qubit element
            update_frequency(qubit_key, df + qubit_IF)
            with for_each_(a,amplitudes):
                # Play the saturation pulse to put the qubit in a mixed state - Can adjust the amplitude on the fly [-2; 2)
                play("x90" * amp(a), qubit_key)
                play("x90" * amp(a), qubit_key)
                play("x90" * amp(a), qubit_key)
                play("x90" * amp(a), qubit_key)
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
        # Cast the data into a 2D matrix, average the 2D matrices together and store the results on the OPX processor
        # Note that the buffering goes from the most inner loop (left) to the most outer one (right)
        I_st.buffer(len(amplitudes)).buffer(len(spec_sweep_dfs)).average().save("I")
        Q_st.buffer(len(amplitudes)).buffer(len(spec_sweep_dfs)).average().save("Q")
        n_st.save("iteration")
        

#####################################
#  Open Communication with the QOP  #
#####################################
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
    fig_live, (ax1, ax2) = plt.subplots(1, 2, sharex=False, figsize=(12, 6.4))
    interrupt_on_close(fig_live, job)  # Interrupts the job when closing the figure
    try:
        while res_handles.is_processing():
            # Fetch results
            iteration, I, Q = res_handles.fetch_all()
            # Convert results into Volts
            I = u.demod2volts(I, readout_len)
            Q = u.demod2volts(Q, readout_len)
            S = I + 1j * Q
            R = np.abs(S)  # Amplitude (shape: [len(pulse_amps), measure_sequence_len])
            phase = np.angle(S)  # Phase
            # Normalize data
            row_sums = R.sum(axis=0)
            R /= row_sums[np.newaxis, :]
            # Progress bar
            progress_counter(iteration, n_avg, start_time=res_handles.get_start_time())
            # Plot results (update axes)
            fig_live.suptitle(f"Qubit {qubit_key} spectroscopy vs amplitude, iteration {iteration+1}/{n_avg}")
            if IQ:
                # 2D color plot: pulse amplitude vs I
                ax1.cla()
                im1 = ax1.pcolormesh(spec_sweep_dfs / u.MHz, amplitudes*control_amp, I.T, shading='auto', cmap='viridis')
                ax1.set_xlabel("Frequency Detuning (MHz)")
                ax1.set_ylabel("Pulse Amplitude (a.u.)")
                ax1.set_title("I")
                if not hasattr(ax1, '_colorbar'):
                    ax1._colorbar = plt.colorbar(im1, ax=ax1, label='I (V)')
                else:
                    ax1._colorbar.update_normal(im1)
                
                # 2D color plot: pulse amplitude vs tau for Q
                ax2.cla()
                im2 = ax2.pcolormesh(spec_sweep_dfs / u.MHz, amplitudes*control_amp, Q.T, shading='auto', cmap='viridis')
                ax2.set_xlabel("Frequency Detuning (MHz)")
                ax2.set_ylabel("Pulse Amplitude (a.u.)")
                ax2.set_title("Q")
                if not hasattr(ax2, '_colorbar'):
                    ax2._colorbar = plt.colorbar(im2, ax=ax2, label='Q (V)')
                else:
                    ax2._colorbar.update_normal(im2)
            else:
                # 2D color plot: pulse amplitude vs tau
                ax1.cla()
                im1 = ax1.pcolormesh(spec_sweep_dfs / u.MHz, amplitudes*control_amp, R.T, shading='auto', cmap='viridis')
                ax1.set_xlabel("Frequency Detuning (MHz)")
                ax1.set_ylabel("Pulse Amplitude (a.u.)")
                ax1.set_title(r"Amplitude $R=\sqrt{I^2 + Q^2}$ (V)")
                if not hasattr(ax1, '_colorbar'):
                    ax1._colorbar = plt.colorbar(im1, ax=ax1, label='R (V)')
                else:
                    ax1._colorbar.update_normal(im1)
                
                # 2D color plot: pulse amplitude vs tau for phase
                ax2.cla()
                phase_unwrapped = np.array([signal.detrend(np.unwrap(phase[:,i])) for i in range(len(amplitudes))])
                im2 = ax2.pcolormesh(spec_sweep_dfs / u.MHz, amplitudes*control_amp, phase_unwrapped, shading='auto', cmap='viridis')
                ax2.set_xlabel("Frequency Detuning (MHz)")
                ax2.set_ylabel("Pulse Amplitude (a.u.)")
                ax2.set_title("Phase (rad)")
                if not hasattr(ax2, '_colorbar'):
                    ax2._colorbar = plt.colorbar(im2, ax=ax2, label='Phase (rad)')
                else:
                    ax2._colorbar.update_normal(im2)
            # ax1.set_yscale('log')
            # ax2.set_yscale('log')
            ax1.set_yscale('linear')
            ax2.set_yscale('linear')
            fig_live.tight_layout()
            fig_live.canvas.draw_idle()
            plt.pause(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user.")

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"I_data": I})
    save_data_dict.update({"Q_data": Q})
    save_data_dict.update({"fig_live": fig_live})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

    # Keep the interactive plot open after acquisition until the user closes it
    message = "Acquisition finished. Close the plot window to continue."
    print(message)
    try:
        # Add a centered text box on the figure (figure coordinates)
        fig_live.text(0.04, 0.98, message, ha='left', va='top', fontsize=8,
                      bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        fig_live.canvas.draw_idle()
    except Exception as e:
        print(e)
    while plt.fignum_exists(fig_live.number):
        plt.pause(0.2)

    qm.close()