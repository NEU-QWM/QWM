"""
        QUBIT SPECTROSCOPY - LONG-TERM MONITORING (e.g. 12 hours)

Repeatedly runs a short, fully-averaged qubit spectroscopy scan and records how the
qubit resonance drifts over time. Each scan is an independent OPX job, so the OPX
result memory never grows and the run can last arbitrarily long. Data is written to
disk incrementally, so an interruption (Ctrl+C, dropped connection) keeps everything
acquired so far.

Recommended usage for drift monitoring:
    - Narrow the span to a few MHz around the known qubit_IF.
    - Use a coarse frequency step and a modest n_avg so each scan takes a few seconds.
    - This gives good time resolution (many traces) over the monitoring window.

Prerequisites:
    - A reasonably well-known qubit_IF (run 04a qubit spectroscopy first).
"""

import time
from datetime import datetime

from qm.qua import *
from qm import QuantumMachinesManager
from configuration import *
from qualang_tools.loops import from_array
import matplotlib.pyplot as plt
from scipy import signal
from qualang_tools.results.data_handler import DataHandler
from macros import single_qubit_parser

from configuration.OPX1000config import *

##################
#   Parameters   #
##################
n_avg = 1000  # Averages per scan. Lower -> faster scans -> better time resolution.

res_key = "r1"
qubit_key = "q1"
required_parameters = ["resonator_key", "readout_len", "qubit_frequency", "qubit_IF", "qubit_relaxation"]
res_key, readout_len, qubit_frequency, qubit_IF, qubit_relaxation = single_qubit_parser(
    multiplexed_parameters.copy(), qubit_key, call_list=required_parameters
)

# thermalization_time = int(qubit_relaxation // 4)  # From ns to clock cycles
thermalization_time = int(10 * u.us // 4)  # From ns to clock cycles (must be an int)

print(f"Qubit frequency is {qubit_IF}")

# ---- Frequency sweep: keep it narrow + coarse for fast scans ----
spec_span = 100 * u.MHz
spec_df = 200 * u.kHz
spec_sweep_dfs = np.arange(-spec_span // 2, spec_span // 2 + spec_df, spec_df)
spec_frequency = spec_sweep_dfs + qubit_frequency

# ---- Monitoring controls ----
monitor_duration = 12 * 3600  # Total monitoring time in seconds (here: 12 hours)
min_scan_interval = 0.0       # Seconds. >0 paces scans (e.g. 60 -> one scan/minute). 0 = back-to-back.
save_interval = 60.0          # Write the dataset to disk at most this often (seconds)

save_dir = Path(__file__).resolve().parent / "data"

###################
# The QUA program #  (one fully-averaged scan; re-run many times from Python)
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)
    df = declare(int)
    I = declare(fixed)
    Q = declare(fixed)
    I_st = declare_stream()
    Q_st = declare_stream()

    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(df, spec_sweep_dfs)):
            update_frequency(qubit_key, df + qubit_IF)
            
            play("x180", qubit_key)

            measure(
                "readout",
                res_key,
                dual_demod.full("cos", "sin", I),
                dual_demod.full("minus_sin", "cos", Q),
            )
            wait(thermalization_time, res_key)
            save(I, I_st)
            save(Q, Q_st)

    with stream_processing():
        I_st.buffer(len(spec_sweep_dfs)).average().save("I")
        Q_st.buffer(len(spec_sweep_dfs)).average().save("Q")


#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)
qm = qmm.open_qm(config, close_other_machines=True)

# Precompile once and re-submit each scan to avoid recompiling every iteration.
# If your qm version lacks queue.add_compiled, replace the two precompile lines and
# the submit line below with:  job = qm.execute(prog)
program_id = qm.compile(prog)

# ---- Storage (grows over the run) ----
elapsed_s = []      # seconds since start of monitoring
R_history = []      # amplitude trace per scan
I_history = []
Q_history = []
peak_detuning = []  # tracked extremum (MHz) per scan, relative to qubit_frequency

# Output file for incremental saving
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
outfile = save_dir / f"monitor_{qubit_key}_{stamp}.npz"
save_dir.mkdir(parents=True, exist_ok=True)


def save_incremental():
    np.savez(
        outfile,
        frequency=spec_frequency,
        detuning=spec_sweep_dfs,
        elapsed_s=np.array(elapsed_s),
        R=np.array(R_history),
        I=np.array(I_history),
        Q=np.array(Q_history),
        peak_detuning_MHz=np.array(peak_detuning),
        qubit_frequency=qubit_frequency,
        n_avg=n_avg,
    )


fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
start = time.time()
last_save = start
scan = 0
print(f"Monitoring qubit {qubit_key} for {monitor_duration / 3600:.1f} h. Press Ctrl+C to stop early.")
print(f"Saving to: {outfile}")

try:
    while time.time() - start < monitor_duration:
        t0 = time.time()

        # ---- Run one scan ----
        pending_job = qm.queue.add_compiled(program_id)
        job = pending_job.wait_for_execution()
        rh = job.result_handles
        rh.wait_for_all_values()
        I = u.demod2volts(rh.get("I").fetch_all(), readout_len)
        Q = u.demod2volts(rh.get("Q").fetch_all(), readout_len)
        S = I + 1j * Q
        R = np.abs(S)
        phase = np.angle(S)

        t = time.time() - start
        elapsed_s.append(t)
        I_history.append(I)
        Q_history.append(Q)
        R_history.append(R)
        # Track the strongest feature (peak or dip) relative to the per-scan baseline
        idx = int(np.argmax(np.abs(R - np.median(R))))
        peak_detuning.append(spec_sweep_dfs[idx] / u.MHz)
        scan += 1

        # ---- Incremental save (time-throttled) ----
        if time.time() - last_save >= save_interval:
            save_incremental()
            last_save = time.time()

        # ---- Progress ----
        per_scan = t / scan
        remaining = monitor_duration - t
        print(
            f"scan {scan} | elapsed {t / 3600:5.2f} h | {per_scan:5.1f} s/scan | "
            f"remaining {remaining / 3600:5.2f} h | peak {peak_detuning[-1]:+.3f} MHz"
        )

        # ---- Live plot ----
        times_h = np.array(elapsed_s) / 3600.0
        R_arr = np.array(R_history)  # shape (n_scans, len_df)

        ax1.cla()
        im = ax1.pcolormesh(spec_sweep_dfs / u.MHz, times_h, R_arr, shading="auto", cmap="viridis")
        ax1.set_xlabel(r"$\Delta f$ (MHz)")
        ax1.set_ylabel("Elapsed time (h)")
        ax1.set_title(f"Qubit {qubit_key} spectroscopy vs time  (scan {scan})")
        if not hasattr(ax1, "_colorbar"):
            ax1._colorbar = plt.colorbar(im, ax=ax1, label="R (V)")
        else:
            ax1._colorbar.update_normal(im)

        ax2.cla()
        ax2.plot(spec_sweep_dfs / u.MHz, R, ".-")
        ax2.set_xlabel(r"$\Delta f$ (MHz)")
        ax2.set_ylabel(r"$R=\sqrt{I^2 + Q^2}$ (V)")
        ax2.set_title(f"Latest two-tone scan (elapsed {t / 3600:.2f} h)")
        ax2.grid(True, alpha=0.3)

        fig.tight_layout()
        fig.canvas.draw_idle()

        # ---- Pace the loop ----
        dt = time.time() - t0
        wait_left = min_scan_interval - dt
        plt.pause(max(0.05, wait_left))

except KeyboardInterrupt:
    print("Monitoring interrupted by user.")
finally:
    # Final save: full arrays + config (kept once, not per scan) via DataHandler
    save_incremental()
    try:
        data_handler = DataHandler(root_data_folder=save_dir)
        save_data_dict = {
            "qubit_key": qubit_key,
            "n_avg": n_avg,
            "frequency": spec_frequency,
            "elapsed_s": np.array(elapsed_s),
            "R": np.array(R_history),
            "I": np.array(I_history),
            "Q": np.array(Q_history),
            "peak_detuning_MHz": np.array(peak_detuning),
            "fig_monitor": fig,
            "config": config,
        }
        data_handler.additional_files = {**default_additional_files}
        script_name = Path(__file__).name
        save_name = "_".join(script_name.split("_")[1:]).split(".")[0].strip().replace(" ", "_")
        data_handler.save_data(data=save_data_dict, name=save_name)
    except Exception as e:
        print(f"DataHandler save failed ({e}); raw .npz at {outfile} is intact.")

    qm.close()
    print(f"Done. {scan} scans over {(time.time() - start) / 3600:.2f} h. Data: {outfile}")

    # Keep the figure open until closed
    print("Close the figure window to exit.")
    while plt.fignum_exists(fig.number):
        plt.pause(0.2)