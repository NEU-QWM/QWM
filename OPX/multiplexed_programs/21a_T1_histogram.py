"""
Repeated T1 measurement.

Runs the standard T1 experiment N times, fits T1 after each run,
and updates a live histogram of the extracted T1 values.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from qm import CompilerOptionArguments

from configuration import *
from configuration.OPX1000config import *

from qualang_tools.results import fetching_tool
from qualang_tools.plot.fitting import Fit

from macros import single_qubit_parser

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


##################
#   Parameters   #
##################

n_runs = 100
n_avg = 20000

qubit_key = "q1"

required_parameters = [
    "resonator_key",
    "readout_len",
    "qubit_frequency",
    "qubit_IF",
    "qubit_relaxation",
    "x180_amp",
]

(
    res_key,
    readout_len,
    qubit_frequency,
    qubit_IF,
    qubit_relaxation,
    x180_amp,
) = single_qubit_parser(
    multiplexed_parameters.copy(),
    qubit_key,
    call_list=required_parameters,
)

thermalization_time = qubit_relaxation // 4

tau_min = 16
tau_max = 36_000
taus = np.logspace(
    np.log10(tau_min),
    np.log10(tau_max),
    200,
    endpoint=True,
)

taus = np.array(np.unique(taus // 4), dtype=int)

print(f"Number of delay points: {len(taus)}")


#########################
# QUA Program Generator #
#########################

def build_t1_program():

    with program() as prog:

        reset_global_phase()

        n = declare(int)
        t = declare(int)

        I = declare(fixed)
        Q = declare(fixed)

        I_st = declare_stream()
        Q_st = declare_stream()
        n_st = declare_stream()

        with for_(n, 0, n < n_avg, n + 1):

            with for_each_(t, taus):

                play("x180", qubit_key)

                wait(t, qubit_key)

                align(qubit_key, res_key)

                measure(
                    "readout",
                    res_key,
                    dual_demod.full(
                        "opt_cos",
                        "opt_sin",
                        I,
                    ),
                    dual_demod.full(
                        "opt_minus_sin",
                        "opt_cos",
                        Q,
                    ),
                )

                wait(
                    thermalization_time,
                    res_key,
                )

                save(I, I_st)
                save(Q, Q_st)

            save(n, n_st)

        with stream_processing():

            I_st.buffer(len(taus)).average().save("I")
            Q_st.buffer(len(taus)).average().save("Q")

            n_st.save("iteration")

    return prog


##############################
# Open Communication to QOP  #
##############################

qmm = QuantumMachinesManager(
    host=qop_ip,
    cluster_name=cluster,
)

qm = qmm.open_qm(
    config,
    close_other_machines=True,
    compiler_options=CompilerOptionArguments(
        flags=["enable-reset-all-phases-at-program-start"]
    ),
)

fit = Fit()

T1_values = []

fig_hist, ax_hist = plt.subplots(figsize=(8, 5))
plt.ion()
plt.show(block=False)

for run_idx in range(n_runs):

    print(
        f"\nRunning T1 #{run_idx+1}/{n_runs}"
    )

    prog = build_t1_program()

    job = qm.execute(prog)

    results = fetching_tool(
        job,
        data_list=["I", "Q", "iteration"],
        mode="wait_for_all",
    )

    I, Q, iteration = results.fetch_all()

    I = u.demod2volts(
        I,
        readout_len,
    )

    Q = u.demod2volts(
        Q,
        readout_len,
    )

    try:

        decay_fit = fit.T1(
            4 * taus,
            Q,
            plot=False,
        )

        T1 = abs(
            decay_fit["T1"][0]
        )

        T1_values.append(T1)

        print(
            f"T1 = {T1:.0f} ns"
        )

    except Exception as e:

        print(
            f"Fit failed: {e}"
        )

        continue

    ax_hist.cla()

    ax_hist.hist(
        T1_values,
        bins="auto",
        edgecolor="black",
        alpha=0.8,
    )

    mean_T1 = np.mean(T1_values)
    std_T1 = np.std(T1_values)

    ax_hist.axvline(
        mean_T1,
        color="red",
        linestyle="--",
        linewidth=2,
        label=(
            f"Mean = {mean_T1:.0f} ns\n"
            f"Std = {std_T1:.0f} ns"
        ),
    )

    ax_hist.set_xlabel(
        "T1 (ns)"
    )

    ax_hist.set_ylabel(
        "Counts"
    )

    ax_hist.set_title(
        f"T1 Distribution\n"
        f"{len(T1_values)}/{n_runs} completed"
    )

    ax_hist.legend()

    fig_hist.canvas.draw_idle()
    plt.pause(0.01)

print("\nFinished.")

T1_values = np.array(T1_values)

print(
    f"\nMean T1 = {np.mean(T1_values):.1f} ns"
)

print(
    f"Std T1  = {np.std(T1_values):.1f} ns"
)

plt.ioff()
plt.show()

qm.close()
