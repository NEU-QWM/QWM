"""
        IQ BLOBS
This sequence involves measuring the state of the resonator 'N' times, first after thermalization (with the qubit
in the |g> state) and then after applying a pi pulse to the qubit (bringing the qubit to the |e> state) successively.
The resulting IQ blobs are displayed, and the data is processed to determine:
    - The rotation angle required for the integration weights, ensuring that the separation between |g> and |e> states
      aligns with the 'I' quadrature.
    - The threshold along the 'I' quadrature for effective qubit state discrimination.
    - The readout fidelity matrix, which is also influenced by the pi pulse fidelity.

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit pi pulse (x180) by running qubit, spectroscopy, rabi_chevron, power_rabi and updated the config.

Next steps before going to the next node:
    - Update the rotation angle (rotation_angle) in the configuration.
    - Update the g -> e threshold (ge_threshold) in the configuration.
"""

from qm.qua import *
from qm import SimulationConfig
from qm import QuantumMachinesManager
from configuration import *
from qualang_tools.analysis.discriminator import two_state_discriminator
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser
import matplotlib.pyplot as plt

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
# Parameters Definition
n_avg = 1000000  # Number of averaging loops
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_frequency", "qubit_IF", "qubit_relaxation", "x180_amp"]
res_key, readout_len, qubit_frequency, qubit_IF, qubit_relaxation, x180_amp = single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)

thermalization_time = qubit_relaxation//4 # From ns to clock cycles

# Data to save
save_data_dict = {
    "qubit_key": qubit_key,
    "n_runs": n_avg,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)
    I_g = declare(fixed)
    Q_g = declare(fixed)
    I_g_st = declare_stream()
    Q_g_st = declare_stream()
    I_e = declare(fixed)
    Q_e = declare(fixed)
    I_e_st = declare_stream()
    Q_e_st = declare_stream()

    with for_(n, 0, n < n_avg, n + 1):
        # Measure the state of the resonator
        measure(
            "readout",
            res_key,
            dual_demod.full("cos", "sin", I_g),
            dual_demod.full("minus_sin", "cos", Q_g),
        )
        # Wait for the qubit to decay to the ground state in the case of measurement induced transitions
        wait(thermalization_time, res_key)
        # Save the 'I' & 'Q' quadratures to their respective streams for the ground state
        save(I_g, I_g_st)
        save(Q_g, Q_g_st)

        align()  # global align
        # Play the x180 gate to put the qubit in the excited state
        play("x180", qubit_key)
        # Align the two elements to measure after playing the qubit pulse.
        align(qubit_key, res_key)
        # Measure the state of the resonator
        measure(
            "readout",
            res_key,
            dual_demod.full("cos", "sin", I_e),
            dual_demod.full("minus_sin", "cos", Q_e),
        )
        # Wait for the qubit to decay to the ground state
        wait(thermalization_time, res_key)
        # Save the 'I' & 'Q' quadratures to their respective streams for the excited state
        save(I_e, I_e_st)
        save(Q_e, Q_e_st)

    with stream_processing():
        # Save all streamed points for plotting the IQ blobs
        I_g_st.save_all("I_g")
        Q_g_st.save_all("Q_g")
        I_e_st.save_all("I_e")
        Q_e_st.save_all("Q_e")

#####################################
#  Open Communication with the QOP  #
#####################################
 
from qm import CompilerOptionArguments
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    # Simulates the QUA program for the specified duration
    simulation_config = SimulationConfig(duration=2_000)  # In clock cycles = 4ns
    # Simulate blocks python until the simulation is done
    job = qmm.simulate(config, prog, simulation_config, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
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
    qm = qmm.open_qm(config, close_other_machines=True, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    # Send the QUA program to the OPX, which compiles and executes it
    job = qm.execute(prog)
    # Creates a result handle to fetch data from the OPX
    res_handles = job.result_handles
    # Waits (blocks the Python console) until all results have been acquired
    res_handles.wait_for_all_values()
    # Fetch the 'I' & 'Q' points for the qubit in the ground and excited states
    Ig = res_handles.get("I_g").fetch_all()["value"]
    Qg = res_handles.get("Q_g").fetch_all()["value"]
    Ie = res_handles.get("I_e").fetch_all()["value"]
    Qe = res_handles.get("Q_e").fetch_all()["value"]
    # Plot the IQ blobs, rotate them to get the separation along the 'I' quadrature, estimate a threshold between them
    # for state discrimination and derive the fidelity matrix
    # Condition to have the Q equal for both states:
    angle = np.arctan2(np.mean(Qe) - np.mean(Qg), np.mean(Ig) - np.mean(Ie))
    C = np.cos(angle)
    S = np.sin(angle)
    # Condition for having e > Ig
    if np.mean((Ig - Ie) * C - (Qg - Qe) * S) > 0:
        angle += np.pi
        C = np.cos(angle)
        S = np.sin(angle)

    Ig_rotated = Ig * C - Qg * S
    Qg_rotated = Ig * S + Qg * C

    Ie_rotated = Ie * C - Qe * S
    Qe_rotated = Ie * S + Qe * C
    from scipy.optimize import minimize
    def _false_detections(threshold, Ig, Ie):
        if np.mean(Ig) < np.mean(Ie):
            false_detections_var = np.sum(Ig > threshold) + np.sum(Ie < threshold)
        else:
            false_detections_var = np.sum(Ig < threshold) + np.sum(Ie > threshold)
        return false_detections_var
    fit = minimize(
        _false_detections,
        0.5 * (np.mean(Ig_rotated) + np.mean(Ie_rotated)),
        (Ig_rotated, Ie_rotated),
        method="Nelder-Mead",
    )
    threshold = fit.x[0]

    gg = np.sum(Ig_rotated < threshold) / len(Ig_rotated)
    ge = np.sum(Ig_rotated > threshold) / len(Ig_rotated)
    eg = np.sum(Ie_rotated < threshold) / len(Ie_rotated)
    ee = np.sum(Ie_rotated > threshold) / len(Ie_rotated)

    fidelity = 100 * (gg + ee) / 2

    if True:
        print(
            f"""
        Fidelity Matrix:
        -----------------
        | {gg:.3f} | {ge:.3f} |
        ----------------
        | {eg:.3f} | {ee:.3f} |
        -----------------
        IQ plane rotated by: {180 / np.pi * angle:.1f}{chr(176)}
        Threshold: {threshold:.3e}
        Fidelity: {fidelity:.1f}%
        """
        )

    if True:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
        ax1.plot(Ig, Qg, ".", alpha=0.1, label="Ground", markersize=2)
        ax1.plot(Ie, Qe, ".", alpha=0.1, label="Excited", markersize=2)
        ax1.axis("equal")
        ax1.legend(["Ground", "Excited"])
        ax1.set_xlabel("I")
        ax1.set_ylabel("Q")
        ax1.set_title("Original Data")

        ax2.plot(Ig_rotated, Qg_rotated, ".", alpha=0.1, label="Ground", markersize=2)
        ax2.plot(Ie_rotated, Qe_rotated, ".", alpha=0.1, label="Excited", markersize=2)
        ax2.axis("equal")
        ax2.set_xlabel("I")
        ax2.set_ylabel("Q")
        ax2.set_title("Rotated Data")

        ax3.hist(Ig_rotated, bins=50, alpha=0.75, label="Ground")
        ax3.hist(Ie_rotated, bins=50, alpha=0.75, label="Excited")
        ax3.axvline(x=threshold, color="k", ls="--", alpha=0.5)
        text_props = dict(
            horizontalalignment="center",
            verticalalignment="center",
            transform=ax3.transAxes,
        )
        ax3.text(0.7, 0.9, f"{threshold:.3e}", text_props)
        ax3.set_xlabel("I")
        ax3.set_title("1D Histogram")

        ax4.imshow(np.array([[gg, ge], [eg, ee]]))
        ax4.set_xticks([0, 1])
        ax4.set_yticks([0, 1])
        ax4.set_xticklabels(labels=["|g>", "|e>"])
        ax4.set_yticklabels(labels=["|g>", "|e>"])
        ax4.set_ylabel("Prepared")
        ax4.set_xlabel("Measured")
        ax4.text(0, 0, f"{100 * gg:.1f}%", ha="center", va="center", color="k")
        ax4.text(1, 0, f"{100 * ge:.1f}%", ha="center", va="center", color="w")
        ax4.text(0, 1, f"{100 * eg:.1f}%", ha="center", va="center", color="w")
        ax4.text(1, 1, f"{100 * ee:.1f}%", ha="center", va="center", color="k")
        ax4.set_title("Fidelities")
        fig.tight_layout()

    # Save results
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"Ig_data": Ig})
    save_data_dict.update({"Qg_data": Qg})
    save_data_dict.update({"Ie_data": Ie})
    save_data_dict.update({"Qe_data": Qe})
    save_data_dict.update({"two_state_discriminator": [angle, threshold, fidelity, gg, ge, eg, ee]})
    save_data_dict.update({"fig":fig})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])
    plt.show()
    qm.close()