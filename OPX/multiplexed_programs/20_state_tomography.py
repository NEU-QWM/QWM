"""
        SINGLE QUBIT STATE TOMOGRAPHY (multiplexed version)

The goal of this program is to measure the projection of the Bloch vector of the qubit along the three axes of the Bloch
sphere in order to reconstruct the full qubit state tomography.
The qubit state preparation is left to the user to define.

Prerequisites:
    - Having found the resonance frequency of the resonator coupled to the qubit under study (resonator_spectroscopy).
    - Having calibrated qubit pi pulse (x180) by running qubit, spectroscopy, rabi_chevron, power_rabi and updated the config.
    - Having calibrated the IQ blobs to perform state discrimination.
    - (optional) Having calibrated the readout (readout_frequency, amplitude, duration_optimization) for better SNR.
    - Set the desired flux bias.
"""

from qm.qua import *
from qm import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import progress_counter, fetching_tool
from macros import readout_macro, single_qubit_parser
import matplotlib.pyplot as plt
from qualang_tools.results.data_handler import DataHandler
from configuration.OPX1000config import *


######################################
# Set-up a Bloch sphere for plotting #
######################################
def bra_tex(s):
    return rf"$\left| {s} \right\rangle$"


class BlochSpherePlot:
    North = np.array((0, 0, 1))
    South = np.array((0, 0, -1))
    East = np.array((1, 0, 0))
    West = np.array((0, 1, 0))

    def __init__(self, elev=20, azim=15, sphere_style=None, circles_style=None, axes_style=None, *args, **kwargs):
        self.fig, self.ax = plt.subplots(subplot_kw={"projection": "3d"}, *args, **kwargs)
        self.ax.view_init(elev=elev, azim=azim)

        self.sphere_style = {"color": "#ccf3ff", "alpha": 0.1}
        if sphere_style:
            self.sphere_style.update(sphere_style)

        self.circles_style = {"color": "#333", "alpha": 0.2, "lw": 1.0}
        if circles_style:
            self.circles_style.update(circles_style)

        self.axes_style = {"color": "#333", "alpha": 0.2, "lw": 1.0}
        if axes_style:
            self.axes_style.update(axes_style)

        self.add_sphere()
        self.add_circles()
        self.add_axes()
        self._prepare_axes()

    def plot_vector(self, v, label=None, **kwargs):
        self.ax.quiver(0, 0, 0, v[0], v[1], v[2], normalize=True, arrow_length_ratio=0.08, **kwargs)
        if label:
            vn = 1.1 * np.array(v) / np.linalg.norm(v)
            self.ax.text(*vn, label, fontsize="large")

    def label(self, position, label, **kwargs):
        self.ax.text(*position, label, fontsize="large", **kwargs)

    def label_bra(self, position, label, **kwargs):
        self.label(position, bra_tex(label), **kwargs)

    def add_circles(self):
        theta = np.linspace(0, 2 * np.pi, 100)
        c = np.cos(theta)
        s = np.sin(theta)
        z = np.zeros_like(theta)
        self.ax.plot(c, s, z, **self.circles_style)
        self.ax.plot(z, c, s, **self.circles_style)
        self.ax.plot(s, z, c, **self.circles_style)

    def add_sphere(self):
        u = np.linspace(0, 2 * np.pi, 100)
        v = np.linspace(0, np.pi, 100)
        x = np.outer(np.cos(u), np.sin(v))
        y = np.outer(np.sin(u), np.sin(v))
        z = np.outer(np.ones_like(u), np.cos(v))
        self.ax.plot_surface(x, y, z, **self.sphere_style)

    def add_axes(self):
        u = np.linspace(-1, 1, 2)
        z = np.zeros_like(u)
        self.ax.plot(u, z, z, **self.axes_style)
        self.ax.plot(z, z, u, **self.axes_style)
        self.ax.plot(z, u, z, **self.axes_style)

    def _prepare_axes(self):
        self.ax.set(aspect="equal")
        self.ax.tick_params(labelbottom=False, labelleft=False)
        self.ax.set_axis_off()
        self.ax.grid(False)
        self.ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        self.ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        self.ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))


##################
#   Parameters   #
##################
qubit_key = "q1"
required_parameters = [
    "resonator_key",
    "qubit_relaxation",
    "ge_threshold",
]
res_key, qubit_relaxation, ge_threshold = (
    single_qubit_parser(multiplexed_parameters.copy(), qubit_key, call_list=required_parameters)
)

thermalization_time = qubit_relaxation // 4  # ns → clock cycles

n_avg = 10000

save_dir = Path(__file__).resolve().parent / "data"
save_data_dict = {
    "qubit_key": qubit_key,
    "n_avg": n_avg,
    "config": config,
}

# Set up Bloch sphere for live plotting
bloch_sphere = BlochSpherePlot(
    sphere_style={"alpha": 0.03, "color": "#333", "shade": False},
    axes_style={"alpha": 0.8},
    elev=20,
    azim=-30,
    dpi=100,
    figsize=(8, 6),
)
bloch_sphere.label_bra(bloch_sphere.North * 1.1, "g")
bloch_sphere.label_bra(bloch_sphere.South * 1.1, "e")
bloch_sphere.label_bra(bloch_sphere.East * 1.1, "X")
bloch_sphere.label_bra(bloch_sphere.West * 1.1, "Y")

###################
# The QUA program #
###################
with program() as prog:
    reset_global_phase()
    n = declare(int)
    state = declare(bool)
    c = declare(int)
    I = declare(fixed)
    Q = declare(fixed)
    state_st = declare_stream()
    n_st = declare_stream()

    with for_(n, 0, n < n_avg, n + 1):
        with for_(c, 0, c <= 2, c + 1):
            # Add here whatever state you want to characterize
            with switch_(c):
                with case_(0):  # projection along X
                    # Map the X-component of the Bloch vector onto the Z-axis (measurement axis)
                    play("-y90", qubit_key)
                    align(qubit_key, res_key)
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    wait(thermalization_time, res_key)
                    save(state, state_st)
                with case_(1):  # projection along Y
                    # Map the Y-component of the Bloch vector onto the Z-axis (measurement axis)
                    play("x90", qubit_key)
                    align(qubit_key, res_key)
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    wait(thermalization_time, res_key)
                    save(state, state_st)
                with case_(2):  # projection along Z
                    state, I, Q = readout_macro(resonator=res_key, threshold=ge_threshold, state=state, I=I, Q=Q)
                    wait(thermalization_time, res_key)
                    save(state, state_st)
        save(n, n_st)

    with stream_processing():
        n_st.save("iteration")
        state_st.boolean_to_int().buffer(3).average().save("states")

#####################################
#  Open Communication with the QOP  #
#####################################
from opx_credentials import qop_ip, cluster
from qm import CompilerOptionArguments
qmm = QuantumMachinesManager(host=qop_ip, cluster_name=cluster)

simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=10_000)
    job = qmm.simulate(config, prog, simulation_config, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    samples = job.get_simulated_samples()
    samples.con1.plot()
    waveform_report = job.get_simulated_waveform_report()
    waveform_dict = waveform_report.to_dict()
    waveform_report.create_plot(samples, plot=True, save_path=str(Path(__file__).resolve()))
else:
    qm = qmm.open_qm(config, close_other_machines=True, compiler_options=CompilerOptionArguments(flags=['enable-reset-all-phases-at-program-start']))
    job = qm.execute(prog)
    results = fetching_tool(job, data_list=["states", "iteration"], mode="live")
    while results.is_processing():
        states, iteration = results.fetch_all()
        progress_counter(iteration, n_avg, start_time=results.get_start_time())
        # Converts the (0,1) -> |g>,|e> convention to (1,-1) -> |g>,|e>
        state = -2 * (states - 0.5)
        bloch_sphere.plot_vector((state[0], state[1], state[2]), "", color="r")
        plt.pause(0.1)

    # Derive the density matrix
    I_mat = np.array([[1, 0], [0, 1]])
    sigma_x = np.array([[0, 1], [1, 0]])
    sigma_y = np.array([[0, -1j], [1j, 0]])
    sigma_z = np.array([[1, 0], [0, -1]])
    # Zero order approximation
    rho = 0.5 * (I_mat + state[0] * sigma_x + state[1] * sigma_y + state[2] * sigma_z)
    print(f"The density matrix is:\n{rho}")

    qm.close()
    script_name = Path(__file__).name
    data_handler = DataHandler(root_data_folder=save_dir)
    save_data_dict.update({"states_data": states})
    data_handler.additional_files = {**default_additional_files}
    data_handler.save_data(data=save_data_dict, name="_".join(script_name.split("_")[1:]).split(".")[0])
