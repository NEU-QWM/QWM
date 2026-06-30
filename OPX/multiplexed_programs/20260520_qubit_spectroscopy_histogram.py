"""
QUBIT SPECTROSCOPY REPEATED (Histogram Mode)

Runs the qubit spectroscopy sequence multiple times, extracts the fitted resonance
frequency each time, and builds a histogram to monitor frequency drift.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from configuration import *
from qualang_tools.results import fetching_tool
from qualang_tools.loops import from_array
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from pathlib import Path
from qualang_tools.plot.fitting import Fit
from macros import single_qubit_parser
from configuration.OPX1000config import *

##################
#   Parameters   #
##################
n_avg = 2000
n_repeats = 50
qubit_key = "q1"

required_parameters = ["resonator_key", "readout_len", "qubit_frequency", "qubit_IF", "qubit_relaxation"]
res_key, readout_len, qubit_frequency, qubit_IF, qubit_relaxation = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

thermalization_time = qubit_relaxation // 4

spec_span = 250 * u.MHz
spec_df = 50 * u.kHz
spec_sweep_dfs = np.arange(-spec_span // 2, spec_span // 2 + spec_df, spec_df)
spec_frequency = spec_sweep_dfs + qubit_frequency

###################
# QUA Program     #
###################
with program() as prog:
    reset_global_phase()

    n = declare(int)
    df = declare(int)
    I = declare(fixed)
    Q = declare(fixed)

    I_st = declare_stream()
    Q_st = declare_stream()
    n_st = declare_stream()

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(df, spec_sweep_dfs)):
            update_frequency(qubit_key, df + qubit_IF)

            play("saturation", qubit_key)

            align(qubit_key, res_key)

            measure(
                "readout",
                res_key,
                dual_demod.full("cos", "sin", I),
                dual_demod.full("minus_sin", "cos", Q),
            )

            wait(thermalization_time, res_key)

            save(I, I_st)
            save(Q, Q_st)

        save(n, n_st)

    with stream_processing():
        n_st.save("iteration")
        I_st.buffer(len(spec_sweep_dfs)).average().save("I")
        Q_st.buffer(len(spec_sweep_dfs)).average().save("Q")

#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

fitted_freqs = []

# Histogram plot (live)
plt.ion()
fig_hist, ax_hist = plt.subplots()

for rep in range(n_repeats):
    print(f"\n--- Run {rep+1}/{n_repeats} ---")

    qm = qmm.open_qm(config, close_other_machines=True)
    job = qm.execute(prog)

    res_handles = fetching_tool(job, data_list=["iteration", "I", "Q"], mode="wait_for_all")

    iteration, I, Q = res_handles.fetch_all()

    # Convert to volts
    I = u.demod2volts(I, readout_len)
    Q = u.demod2volts(Q, readout_len)

    S = I + 1j * Q
    R = np.abs(S)
    phase = np.angle(S)

    qm.close()

    # ---- FIT ----
    try:
        fit = Fit()
        spec_fit = fit.transmission_resonator_spectroscopy(
            (spec_frequency) / u.MHz, R, plot=False
        )

        f_peak = spec_fit["f"][0]  # MHz
        fitted_freqs.append(f_peak)

        print(f"Run {rep+1}: Peak = {f_peak:.6f} MHz")

    except Exception as e:
        print(f"Fit failed on run {rep+1}")
        continue

    # ---- LIVE HISTOGRAM UPDATE ----
    ax_hist.cla()
    ax_hist.hist(fitted_freqs, bins=min(10, len(fitted_freqs)), edgecolor="black")

    mean_f = np.mean(fitted_freqs)
    std_f = np.std(fitted_freqs)

    ax_hist.axvline(mean_f, color="r", linestyle="--", label=f"Mean = {mean_f:.6f} MHz")
    ax_hist.set_title("Qubit Frequency Drift Histogram")
    ax_hist.set_xlabel("Frequency (MHz)")
    ax_hist.set_ylabel("Counts")
    ax_hist.legend()

    fig_hist.canvas.draw()
    fig_hist.canvas.flush_events()

##################
# Final Results  #
##################
fitted_freqs = np.array(fitted_freqs)

mean_f = np.mean(fitted_freqs)
std_f = np.std(fitted_freqs)

print("\n========== FINAL RESULTS ==========")
print(f"Mean frequency: {mean_f:.6f} MHz")
print(f"Std deviation: {std_f*1e3:.3f} kHz")

# Keep histogram open
plt.ioff()
plt.show()