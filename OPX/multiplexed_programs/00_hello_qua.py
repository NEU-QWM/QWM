"""
A simple sandbox to showcase different QUA functionalities during the installation.
"""
from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from qualang_tools.results import progress_counter, fetching_tool

from configuration.OPX1000config import *

a_min = 0.0
a_max = 1.5
a_step = 0.4
np.arange(a_min, a_max + a_step, a_step)
n_avg = 8

###################
# The QUA program #
###################
with program() as hello_qua:
    reset_global_phase()
    n1 = declare(int)
    n2 = declare(int)
    n1_st = declare_stream()
    n2_st = declare_stream()
    with if_(True):
        assign(n1, 1)
        assign(n2, 2)
    save(n1, n1_st)
    assign(n1, n1 * n2)
    save(n1, n1_st)
    save(n1, n1_st)

    with stream_processing():
        n1_st.timestamps().save_all("n1")

#####################################
#  Open Communication with the QOP  #
#####################################
from opx_credentials import qop_ip, cluster
from qm import CompilerOptionArguments
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

###########################
# Run or Simulate Program #
########################### 

simulate = False
if simulate:
    # Simulates the QUA program for the specified duration
    simulation_config = SimulationConfig(duration=2_000, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))  # In clock cycles = 4ns
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
    qm = qmm.open_qm(config, close_other_machines=True, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    # Send the QUA program to the OPX, which compiles and executes it - Execute does not block python!
    job = qm.execute(hello_qua)

    results = fetching_tool(job, data_list=["n1"], mode="wait_for_all")

    print(results.fetch_all())  # Fetch all results at once