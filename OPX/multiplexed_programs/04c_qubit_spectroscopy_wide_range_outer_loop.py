"""
        QUBIT SPECTROSCOPY OVER A WIDE RANGE (OUTER LOOP)
This procedure conducts a broad 1D frequency sweep of the qubit, measuring the resonator while sweeping an
external LO source simultaneously. The external LO source is swept in the outer loop to optimize run time.
Users should update the LO source frequency using the provided API at the end of the script
(lo_source.set_freq(freqs_external[i])).

Prerequisites:
    - Identification of the resonator's resonance frequency when coupled to the qubit (resonator_spectroscopy).
    - Configuration of the saturation pulse amplitude and duration to transition the qubit into a mixed state.

Before proceeding to the next node:
    - Adjust the qubit frequency settings, labeled as "qubit_IF" and "qubit_LO", in the configuration.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qualang_tools.results import progress_counter
from qualang_tools.plot import interrupt_on_close
from qualang_tools.loops import from_array
import matplotlib.pyplot as plt
from time import sleep
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_IF", "qubit_frequency", "qubit_relaxation"]
res_key, readout_len, qubit_IF, qubit_frequency, qubit_relaxation = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles

n_avg = 50000  # Number of averages
# Intermediate frequency sweep parameters
f_min = 300 * u.MHz
f_max = 400 * u.MHz
df = 250 * u.kHz
frequencies = np.arange(f_min, f_max + 0.1, df)

# External LO frequency sweep (covers the gap between the IF range and the target qubit frequency range)
f_min_external = 3.0e9 - f_min
f_max_external = 5.9e9 - f_max
df_external = f_max - f_min
freqs_external = np.arange(f_min_external, f_max_external + 0.1, df_external)
frequency = np.array(np.concatenate([frequencies + freqs_external[i] for i in range(len(freqs_external))]))

# ---- Data to save ---- #
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "IF_frequencies": frequencies,
    "external_frequencies": freqs_external,
    "frequencies": frequency,
    "config": config,
}
save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)    # averaging loop
    i = declare(int)    # LO frequency loop
    f = declare(int)    # qubit IF
    I = declare(fixed)
    Q = declare(fixed)
    I_st = declare_stream()
    Q_st = declare_stream()
    n_st = declare_stream()

    with for_(i, 0, i < len(freqs_external) + 1, i + 1):
        pause()  # Waits until resumed from Python (LO update)
        with for_(n, 0, n < n_avg, n + 1):
            with for_(*from_array(f, frequencies)):
                update_frequency(qubit_key, f)
                align(qubit_key, res_key)
                play("saturation", qubit_key)
                wait(10*u.us, res_key)
                measure(
                    "readout",
                    res_key,
                    dual_demod.full("cos", "sin", I),
                    dual_demod.full("minus_sin", "cos", Q),
                )
                wait(thermalization_time, res_key)
                save(I, I_st)
                save(Q, Q_st)
        save(i, n_st)

    with stream_processing():
        I_st.buffer(len(frequencies)).buffer(n_avg).map(FUNCTIONS.average()).save_all("I")
        Q_st.buffer(len(frequencies)).buffer(n_avg).map(FUNCTIONS.average()).save_all("Q")
        n_st.save_all("iteration")

#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)


def wait_until_job_is_paused(current_job):
    """Polls until the OPX FPGA reaches the pause statement."""
    while not current_job.is_paused():
        sleep(0.1)
    return True


###############
# Run Program #
###############
qm = qmm.open_qm(config, close_other_machines=True)
job = qm.execute(prog)
res_handles = job.result_handles
I_handle = res_handles.get("I")
Q_handle = res_handles.get("Q")
n_handle = res_handles.get("iteration")

I_tot = []
Q_tot = []
fig = plt.figure()
interrupt_on_close(fig, job)

for i in range(len(freqs_external)):
    # Set the LO frequency – replace with your own hardware API call:
    # lo_source.set_freq(freqs_external[i])
    job.set_converter_frequency("qubit", freqs_external[i])
    print(f"Set LO to {freqs_external[i] / 1e9:.4f} GHz  [implement lo_source.set_freq()]")
    job.resume()
    wait_until_job_is_paused(job)
    I_handle.wait_for_values(i + 1)
    Q_handle.wait_for_values(i + 1)
    n_handle.wait_for_values(i + 1)
    I = np.concatenate(I_handle.fetch(i)["value"])
    Q = np.concatenate(Q_handle.fetch(i)["value"])
    I_tot.append(I)
    Q_tot.append(Q)
    progress_counter(i, len(freqs_external))
    S = u.demod2volts(I + 1j * Q, readout_len)
    R = np.abs(S)
    phase = np.angle(S)
    plt.suptitle(f"Qubit {qubit_key} spectroscopy (wide range)")
    ax1 = plt.subplot(211)
    plt.plot((frequencies + freqs_external[i]) / u.MHz, R, ".")
    plt.xlabel("Qubit frequency (MHz)")
    plt.ylabel(r"$\sqrt{I^2 + Q^2}$ (V)")
    plt.subplot(212, sharex=ax1)
    plt.plot((frequencies + freqs_external[i]) / u.MHz, phase, ".")
    plt.xlabel("Qubit frequency (MHz)")
    plt.ylabel("Phase (rad)")
    plt.pause(0.1)
    plt.tight_layout()
plt.show()

# job.halt()
I = np.concatenate(I_tot)
Q = np.concatenate(Q_tot)
S = u.demod2volts(I + 1j * Q, readout_len)
R = np.abs(S)
phase = np.angle(S)

fig_final = plt.figure()
plt.suptitle(f"Qubit {qubit_key} wide-range spectroscopy")
ax1 = plt.subplot(211)
plt.plot(frequency / u.MHz, R, ".")
plt.xlabel("Qubit frequency (MHz)")
plt.ylabel(r"$\sqrt{I^2 + Q^2}$ (V)")
plt.subplot(212, sharex=ax1)
plt.plot(frequency / u.MHz, phase, ".")
plt.xlabel("Qubit frequency (MHz)")
plt.ylabel("Phase (rad)")
plt.tight_layout()
plt.pause(0.1)
plt.show()

# Save results
script_name = Path(__file__).name
data_handler = DataHandler(root_data_folder=save_dir)
save_data_dict.update({"I_data": I, "Q_data": Q})
save_data_dict.update({"fig_live": fig})
save_data_dict.update({"fig_final": fig_final})

data_handler.additional_files = {**default_additional_files}
data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])

qm.close()
