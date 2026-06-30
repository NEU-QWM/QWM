"""
        QUBIT SPECTROSCOPY
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
n_avg = 1000  # Number of averaging loops
n_rep = 100   # Number of repetition loops
repetitions = np.arange(1, n_rep + 1)

res_key = "r1"
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_frequency", "qubit_IF", "qubit_relaxation"]
res_key, readout_len, qubit_frequency, qubit_IF, qubit_relaxation = single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)

# thermalization_time = qubit_relaxation // 4  # From ns to clock cycles
thermalization_time = int(4 * u.us // 4)  # From ns to clock cycles (must be an int number of clock cycles)

print(f"Qubit frequency is {qubit_IF}")

spec_span = 100 * u.MHz
spec_df = 200 * u.kHz
spec_sweep_dfs = np.arange(-spec_span // 2, spec_span // 2 + spec_df, spec_df)
spec_frequency = spec_sweep_dfs + qubit_frequency

# ---- Data to save ---- #
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "frequency": spec_frequency,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)    # QUA variable for the averaging loop
    r = declare(int)    # QUA variable for the repetition loop
    df = declare(int)   # QUA variable for the qubit frequency detuning
    I = declare(fixed)  # QUA variable for the measured 'I' quadrature
    Q = declare(fixed)  # QUA variable for the measured 'Q' quadrature
    I_st = declare_stream()  # Stream for the 'I' quadrature
    Q_st = declare_stream()  # Stream for the 'Q' quadrature
    n_st = declare_stream()  # Stream for the repetition index (drives the progress bar)

    # Loop over the repetitions (kept as a QUA loop so everything feeds a single, named result stream)
    with for_(r, 0, r < n_rep, r + 1):
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
        # Save the repetition index once per repetition to drive the progress bar
        save(r, n_st)

    with stream_processing():
        # Stream order is (r outer, n middle, df inner).
        # buffer(len_df)  -> one frequency sweep per shot
        # buffer(n_avg)   -> stack the n_avg sweeps of one repetition
        # average over n_avg, then save_all so each repetition streams out live -> final shape (n_rep, len_df)
        I_st.buffer(len(spec_sweep_dfs)).buffer(n_avg).map(FUNCTIONS.average()).save_all("I")
        Q_st.buffer(len(spec_sweep_dfs)).buffer(n_avg).map(FUNCTIONS.average()).save_all("Q")
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
    res_handles = fetching_tool(job, data_list=["iteration", "I", "Q"], mode="live")
    # Waits (blocks the Python console) until all results have been acquired
    IQ = False
    fig_live, (ax1, ax2) = plt.subplots(1, 2, sharex=False, figsize=(12, 6.4))
    interrupt_on_close(fig_live, job)  # Interrupts the job when closing the figure
    try:
        while res_handles.is_processing():
            # Fetch results
            iteration, I, Q = res_handles.fetch_all()
            # 'save_all' returns a structured array with a 'value' field (plus timestamps).
            # Extract the raw demod values -> shape (completed_reps, len(dfs)).
            if I.dtype.names is not None and "value" in I.dtype.names:
                I = I["value"]
            if Q.dtype.names is not None and "value" in Q.dtype.names:
                Q = Q["value"]
            # Convert results into Volts. I/Q stream out as (completed_reps, len(dfs)).
            I = u.demod2volts(I, readout_len)
            Q = u.demod2volts(Q, readout_len)
            # Transpose to (len(dfs), completed_reps) so the frequency axis is rows and repetitions are columns
            I = np.atleast_2d(I).T
            Q = np.atleast_2d(Q).T
            # Number of repetitions acquired so far (grows live until it reaches n_rep)
            reps_axis = np.arange(1, I.shape[1] + 1)
            S = I + 1j * Q
            R = np.abs(S)  # Amplitude (shape: [len(dfs), completed_reps])
            phase = np.angle(S)  # Phase
            # Normalize data per repetition (column)
            row_sums = R.sum(axis=0)
            R = R / row_sums[np.newaxis, :]
            print(np.shape(R))
            # Progress bar over repetitions
            progress_counter(iteration, n_rep, start_time=res_handles.get_start_time())
            # Plot results (update axes)
            fig_live.suptitle(f"Qubit {qubit_key} spectroscopy, repetition {int(iteration) + 1}/{n_rep}")
            if IQ:
                # 2D color plot: frequency vs repetition for I
                ax1.cla()
                im1 = ax1.pcolormesh(spec_sweep_dfs / u.MHz, reps_axis, I.T, shading='auto', cmap='viridis')
                ax1.set_xlabel("Frequency Detuning (MHz)")
                ax1.set_ylabel("Repetitions")
                ax1.set_title("I")
                if not hasattr(ax1, '_colorbar'):
                    ax1._colorbar = plt.colorbar(im1, ax=ax1, label='I (V)')
                else:
                    ax1._colorbar.update_normal(im1)

                # 2D color plot: frequency vs repetition for Q
                ax2.cla()
                im2 = ax2.pcolormesh(spec_sweep_dfs / u.MHz, reps_axis, Q.T, shading='auto', cmap='viridis')
                ax2.set_xlabel("Frequency Detuning (MHz)")
                ax2.set_ylabel("Repetitions")
                ax2.set_title("Q")
                if not hasattr(ax2, '_colorbar'):
                    ax2._colorbar = plt.colorbar(im2, ax=ax2, label='Q (V)')
                else:
                    ax2._colorbar.update_normal(im2)
            else:
                # 2D color plot: frequency vs repetition for amplitude
                ax1.cla()
                im1 = ax1.pcolormesh(spec_sweep_dfs / u.MHz, reps_axis, R.T, shading='auto', cmap='viridis')
                ax1.set_xlabel("Frequency Detuning (MHz)")
                ax1.set_ylabel("Repetitions")
                ax1.set_title(r"Amplitude $R=\sqrt{I^2 + Q^2}$ (V)")
                if not hasattr(ax1, '_colorbar'):
                    ax1._colorbar = plt.colorbar(im1, ax=ax1, label='R (V)')
                else:
                    ax1._colorbar.update_normal(im1)

                # 2D color plot: frequency vs repetition for phase
                ax2.cla()
                phase_unwrapped = np.array(
                    [signal.detrend(np.unwrap(phase[:, i])) for i in range(len(reps_axis))]
                )
                im2 = ax2.pcolormesh(spec_sweep_dfs / u.MHz, reps_axis, phase_unwrapped, shading='auto', cmap='viridis')
                ax2.set_xlabel("Frequency Detuning (MHz)")
                ax2.set_ylabel("Repetitions")
                ax2.set_title("Phase (rad)")
                if not hasattr(ax2, '_colorbar'):
                    ax2._colorbar = plt.colorbar(im2, ax=ax2, label='Phase (rad)')
                else:
                    ax2._colorbar.update_normal(im2)
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
        # Add a text box on the figure (figure coordinates)
        fig_live.text(0.04, 0.98, message, ha='left', va='top', fontsize=8,
                      bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        fig_live.canvas.draw_idle()
    except Exception as e:
        print(e)
    while plt.fignum_exists(fig_live.number):
        plt.pause(0.2)

    qm.close()