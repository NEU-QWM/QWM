"""
A simple sandbox to showcase different QUA functionalities during the installation.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from pathlib import Path

import numpy as np
from qualang_tools.units import unit

u = unit(coerce_to_integer=True)

span = 20 * u.MHz
dfs = np.arange(-span, span, 1 * u.MHz)

def rs_iter():
    update_frequency("resonator", resonator_IF + df)
    measure(
        "readout",
        "resonator",
        dual_demod.full("cos", "sin", I),
        dual_demod.full("minus_sin", "cos", Q),
    )

###################
# The QUA program #
###################
with program() as hello_qua:
    df = declare(int)
    I = declare(fixed)
    Q = declare(fixed)
    with for_(df, -span, df < span, df + 1*u.MHz):
        rs_iter()
        wait(100)

#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster_name)

###########################
# Run or Simulate Program #
###########################

simulate = True

if simulate:
    # Simulates the QUA program for the specified duration
    simulation_config = SimulationConfig(duration=10_000)  # In clock cycles = 4ns
    # Simulate blocks python until the simulation is done
    # Simulate blocks python until the simulation is done
    job = qmm.simulate(config, hello_qua, simulation_config)
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
    # Open a quantum machine to execute the QUA program
    qm = qmm.open_qm(config)
    # Send the QUA program to the OPX, which compiles and executes it - Execute does not block python!
    job = qm.execute(hello_qua)
