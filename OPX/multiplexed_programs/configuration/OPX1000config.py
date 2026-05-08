
from pathlib import Path
import os
from qualang_tools.config.waveform_tools import drag_gaussian_pulse_waveforms
import numpy as np
from qualang_tools.units import unit
u = unit(coerce_to_integer=True)

qop_ip = "172.31.255.63"
cluster = "Cluster_1"

con = "con1" # Controller name in OPX1000
mw_fem = 1 # MW-FEM slot in OPX1000
lf_fem = 5  # LF-FEM slot in OPX1000 (for flux lines)
sampling_rate = int(1e9)  # or, int(2e9)
'''
Port setup, flux tunable transmons
OPX resonator output: con1, fem1, ch2
OPX resonator input: con1, fem1, ch2
OPX qubit output:    con1, fem1, ch4
OPX flux lines:      con1, fem2, ch1..num_qubits
'''
resonator_analogOutput = (con, mw_fem, 2) # Controller, FEM, channel
resonator_analogInput = (con, mw_fem, 1) # Controller, FEM, channel
qubit_analogOutput = [(con, mw_fem, 6), (con, mw_fem, 6), (con, mw_fem, 6)] # Controller, FEM, channel

num_qubits = 1
#########################################
# %% ---- Flux line parameters ---- #
#########################################
_flux_keys = [f"fl{i+1}" for i in range(num_qubits)]
_max_frequency_points = np.array([0.0] * num_qubits)  # DC offset (V) for maximum qubit frequency point
_flux_settle_times = [100] * num_qubits  # ns - flux settle time after changing bias
_const_flux_lens = [200] * num_qubits  # ns - default constant flux pulse duration
_const_flux_amps = np.array([0.45] * num_qubits)  # V  - default constant flux pulse amplitude

# Resonator frequency versus flux fit parameters per qubit (from resonator_spectroscopy_vs_flux)
# Model: amplitude * np.cos(2 * np.pi * frequency * x + phase) + offset
_amplitude_fits = np.array([0.0] * num_qubits)
_frequency_fits = np.array([0.0] * num_qubits)
_phase_fits = np.array([0.0] * num_qubits)
_offset_fits = np.array([0.0] * num_qubits)

#####################################
# %% ---- Resonator parameters ---- #
#####################################
_resonator_keys = [f"r{i+1}" for i in range(num_qubits)]
# _resonator_frequency = np.array([6750, 6701.889835, 6750]) * u.MHz
_resonator_frequency = np.array([6165.31, 6447.73, 6701.95]) * u.MHz
_resonator_LO = (6300) * u.MHz
_resonator_IF = _resonator_frequency - _resonator_LO
_resonator_relaxation_times = [3_000] * num_qubits
resonator_LO_band = 2
resonator_power = 2 # dBm
print(1_000*5_00_0)
# Readout optimization
_readout_lens = [500] * num_qubits# ns
_readout_amplitudes = np.array([0.15]*num_qubits) #0.3
_rotation_angles = (np.array([235.6, 0.0, 0.0, 0.0, 0.0, 0.0]) / 180) * np.pi
_ge_thresholds = np.array([9.981e-07, 0.0, 0.0, 0.0, 0.0, 0.0]) # Ge thresholds for each qubit
time_of_flight = 396 # ns

default_additional_files = {
    # Path(__file__).name: Path(__file__).name,
}

# Piecing together optimal weights if available
opt_weights_real = []
opt_weights_minus_imag = []
opt_weights_imag = []
opt_weights_minus_real = []
loaded = []
not_loaded = []
for i, _res_key in enumerate(_resonator_keys):
    try:
        weights = np.load(os.path.join(os.path.dirname(__file__), f"optimal_weights_{_res_key}.npz"))
        opt_weights_real.append([(int(x), int(weights["division_length"] * 4)) for x in weights["weights_real"]])
        opt_weights_minus_imag.append([(int(x), int(weights["division_length"] * 4)) for x in weights["weights_minus_imag"]])
        opt_weights_imag.append([(int(x), int(weights["division_length"] * 4)) for x in weights["weights_imag"]])
        opt_weights_minus_real.append([(int(x), int(weights["division_length"] * 4)) for x in weights["weights_minus_real"]])
        default_additional_files[f"optimal_weights_{_res_key}.npz"] = f"optimal_weights_{_res_key}.npz"
        #print(f"Loaded optimal weights for resonator {_res_key}.")
        loaded.append(_res_key)
    except Exception as e:
        # print(f"Could not load optimal weights for resonator {_res_key}. Using default rotated weights. Error: {e}")
        not_loaded.append(_res_key)
        opt_weights_real.append([(np.cos(_rotation_angles[i]), _readout_lens[i])])
        opt_weights_minus_imag.append([(np.sin(_rotation_angles[i]), _readout_lens[i])])
        opt_weights_imag.append([(-np.sin(_rotation_angles[i]), _readout_lens[i])])
        opt_weights_minus_real.append([(-np.cos(_rotation_angles[i]), _readout_lens[i])])
print(f"Loaded optimal weights for resonators: {loaded}")
print(f"Could not load optimal weights for resonators: {not_loaded}")

# ---- Populate the resonator elements ---- #
resonator_elements = {}
readout_pulses = {}
readout_waveforms = {}
readout_integration_weights = {}
for i, key in enumerate(_resonator_keys):
    ii = i + 1
    resonator_elements[key] = {
        "MWInput":{
            "port":resonator_analogOutput,
            "upconverter": 1, # which upconverter to use (if shared)
        },
        "intermediate_frequency": _resonator_IF[i],
        "MWOutput":{
            "port":resonator_analogInput,
        },
        "operations":{
            "cw": "const_pulse",
            "readout": f"readout_pulse_{ii}",
            "x180": f"x180_pulse_{ii}",
        },
        "time_of_flight":time_of_flight,
    }
    readout_pulses[f"readout_pulse_{ii}"] = {
        "operation": "measurement",
        "length": _readout_lens[i],
        "waveforms": {
            "I": f"readout_wf_{ii}",
            "Q": "zero_wf",
        },
        "integration_weights": {
            "cos": f"cosine_weights_{ii}",
            "sin": f"sine_weights_{ii}",
            "minus_sin": f"minus_sine_weights_{ii}",
            "rotated_cos": f"rotated_cosine_weights_{ii}",
            "rotated_sin": f"rotated_sine_weights_{ii}",
            "rotated_minus_sin": f"rotated_minus_sine_weights_{ii}",
            "opt_cos": f"opt_cosine_weights_{ii}",
            "opt_sin": f"opt_sine_weights_{ii}",
            "opt_minus_sin": f"opt_minus_sine_weights_{ii}",
        },
        "digital_marker": "ON",
    }
    readout_waveforms[f"readout_wf_{ii}"] = {"type": "constant", "sample": _readout_amplitudes[i]}

    integration_time = 1_000
    readout_integration_weights_i = {
        f"cosine_weights_{ii}": {
            "cosine": [(1.0, integration_time)],
            "sine": [(0.0, integration_time)],
        },
        f"sine_weights_{ii}": {
            "cosine": [(0.0, integration_time)],
            "sine": [(1.0, integration_time)],
        },
        f"minus_sine_weights_{ii}": {
            "cosine": [(0.0, integration_time)],
            "sine": [(-1.0, integration_time)],
        },
        f"rotated_cosine_weights_{ii}": {
            "cosine": [(np.cos(_rotation_angles[i]), _readout_lens[i])],
            "sine": [(np.sin(_rotation_angles[i]), _readout_lens[i])],
        },
        f"rotated_sine_weights_{ii}": {
            "cosine": [(-np.sin(_rotation_angles[i]), _readout_lens[i])],
            "sine": [(np.cos(_rotation_angles[i]), _readout_lens[i])],
        },
        f"rotated_minus_sine_weights_{ii}": {
            "cosine": [(np.sin(_rotation_angles[i]), _readout_lens[i])],
            "sine": [(-np.cos(_rotation_angles[i]), _readout_lens[i])],
        },
        f"opt_cosine_weights_{ii}": {
            "cosine": opt_weights_real[i],
            "sine": opt_weights_minus_imag[i],
        },
        f"opt_sine_weights_{ii}": {
            "cosine": opt_weights_imag[i],
            "sine": opt_weights_real[i],
        },
        f"opt_minus_sine_weights_{ii}": {
            "cosine": opt_weights_minus_imag[i],
            "sine": opt_weights_minus_real[i],
        },
    }
    readout_integration_weights = {**readout_integration_weights, **readout_integration_weights_i}

#################################
# %% ---- Qubit parameters ---- #
#################################
_qubit_keys = [f"q{i+1}" for i in range(num_qubits)]
# _qubit_frequency = np.array([4855.0]*num_qubits) * u.MHz # center frequency
_qubit_frequency = np.array([4865.811920]*num_qubits) * u.MHz # left peak
# _qubit_frequency = np.array([4867.866598]*num_qubits) * u.MHz # right peak
_qubit_LO = _qubit_frequency + 47.0 * u.MHz
_qubit_IF = _qubit_frequency - _qubit_LO
_qubit_relaxation_times = [3_000] * num_qubits # ns
qubit_LO_band = [1, 2, 2]
qubit_power = [16, 4, 4] # dBm


# ---- Qubit operation parameters ---- #
# Drag pulse parameters
_x180_lens = [232, 40, 40, 40, 40, 40] # ns  #612
_x180_amplitudes = np.array([1.0, 0.3, 0.3, 0.3, 0.3, 0.3]) # Amplitude for 180 pulse
_x90_lens = _x180_lens # ns
_x90_amplitudes = _x180_amplitudes / 2 # Amplitude for 90 pulse
_drag_coefficients = np.array([0.01, 0.01, 0.01, 0.01, 0.01, 0.01]) # DRAG coefficients
_anharmonicities = np.ones(_x180_amplitudes.shape) * -150 * u.MHz
_AC_stark_detunings = np.ones(_x180_amplitudes.shape) * 0.0 * u.MHz

# Saturation_pulse
saturation_len = 0.232 * u.us
saturation_amp = 1.0
# Square pi pulse
square_pi_len = 160
square_pi_amp = 0.5
# Constant pulse parameters 
const_len = 100
const_amp = 0.03

# Store control amplitude
_control_amp = np.array([saturation_amp]*num_qubits)

# ---- Drag pulse parameters & generation ---- #
def generate_drag_x180(drag_coef, anharmonicity, AC_stark_detuning, x180_len, x180_amp):
    x180_sigma = x180_len / 5
    x180_wf, x180_der_wf = np.array(
        drag_gaussian_pulse_waveforms(x180_amp, x180_len, x180_sigma, drag_coef, anharmonicity, AC_stark_detuning)
    )
    x180_I_wf = x180_wf
    x180_Q_wf = x180_der_wf
    # No DRAG when alpha=0, it's just a gaussian.
    return x180_I_wf, x180_Q_wf, int(x180_len), x180_amp

def generate_drag_x90(drag_coef, anharmonicity, AC_stark_detuning, x90_len, x90_amp):
    x90_sigma = x90_len / 5
    x90_wf, x90_der_wf = np.array(
        drag_gaussian_pulse_waveforms(x90_amp, x90_len, x90_sigma, drag_coef, anharmonicity, AC_stark_detuning)
    )
    x90_I_wf = x90_wf
    x90_Q_wf = x90_der_wf
    # No DRAG when alpha=0, it's just a gaussian.
    return x90_I_wf, x90_Q_wf, int(x90_len), x90_amp

def generate_drag_minus_x90(drag_coef, anharmonicity, AC_stark_detuning, minus_x90_len, minus_x90_amp):
    minus_x90_sigma = minus_x90_len / 5
    minus_x90_wf, minus_x90_der_wf = np.array(
        drag_gaussian_pulse_waveforms(
            minus_x90_amp,
            minus_x90_len,
            minus_x90_sigma,
            drag_coef,
            anharmonicity,
            AC_stark_detuning,
        )
    )
    minus_x90_I_wf = minus_x90_wf
    minus_x90_Q_wf = minus_x90_der_wf
    # No DRAG when alpha=0, it's just a gaussian.
    return minus_x90_I_wf, minus_x90_Q_wf, int(minus_x90_len), minus_x90_amp

def generate_drag_y180(drag_coef, anharmonicity, AC_stark_detuning, y180_len, y180_amp):
    y180_sigma = y180_len / 5
    y180_wf, y180_der_wf = np.array(
        drag_gaussian_pulse_waveforms(y180_amp, y180_len, y180_sigma, drag_coef, anharmonicity, AC_stark_detuning)
    )
    y180_I_wf = (-1) * y180_der_wf
    y180_Q_wf = y180_wf
    # No DRAG when alpha=0, it's just a gaussian.
    return y180_I_wf, y180_Q_wf, int(y180_len), y180_amp

def generate_drag_minus_y90(drag_coef, anharmonicity, AC_stark_detuning, y90_len, y90_amp):
    y90_sigma = y90_len / 5
    y90_wf, y90_der_wf = np.array(
        drag_gaussian_pulse_waveforms(y90_amp, y90_len, y90_sigma, drag_coef, anharmonicity, AC_stark_detuning)
    )
    y90_I_wf = (-1) * y90_der_wf
    y90_Q_wf = y90_wf
    # No DRAG when alpha=0, it's just a gaussian.
    return y90_I_wf, y90_Q_wf, int(y90_len), y90_amp

def generate_drag_minus_y90(drag_coef, anharmonicity, AC_stark_detuning, minus_y90_len, minus_y90_amp):
    minus_y90_sigma = minus_y90_len / 5
    minus_y90_wf, minus_y90_der_wf = np.array(
        drag_gaussian_pulse_waveforms(
            minus_y90_amp,
            minus_y90_len,
            minus_y90_sigma,
            drag_coef,
            anharmonicity,
            AC_stark_detuning,
        )
    )
    minus_y90_I_wf = (-1) * minus_y90_der_wf
    minus_y90_Q_wf = minus_y90_wf
    # No DRAG when alpha=0, it's just a gaussian.
    return minus_y90_I_wf, minus_y90_Q_wf, int(minus_y90_len), minus_y90_amp

# ---- Populate the qubit elements ---- #
qubit_elements = {}
qubit_pulses = {}
qubit_waveforms = {}
for i, key in enumerate(_qubit_keys):
    ii = i + 1
    qubit_elements[key] = {
        "MWInput":{
            "port":qubit_analogOutput[i],
            "upconverter": 1, # which upconverter to use (if shared)
        },
        "intermediate_frequency": _qubit_IF[i],
        "operations":{
            "cw": "const_pulse",
            "saturation": "saturation_pulse",
            "pi": "pi_pulse",
            "pi_half": "pi_half_pulse",
            "x180": f"x180_pulse_{ii}",
            "x90": f"x90_pulse_{ii}",
            "-x90": f"-x90_pulse_{ii}",
            "y90": f"y90_pulse_{ii}",
            "y180": f"y180_pulse_{ii}",
            "-y90": f"-y90_pulse_{ii}",
        },
    }
    x90_I_wf, x90_Q_wf, _x90_len, _x90_amp = generate_drag_x90(_drag_coefficients[i], _anharmonicities[i], _AC_stark_detunings[i], _x90_lens[i], _x90_amplitudes[i])
    x180_I_wf, x180_Q_wf, _x180_len, _x180_amp = generate_drag_x180(_drag_coefficients[i], _anharmonicities[i], _AC_stark_detunings[i], _x180_lens[i], _x180_amplitudes[i])
    minus_x90_I_wf, minus_x90_Q_wf, _minus_x90_len, _minus_x90_amp = generate_drag_minus_x90(_drag_coefficients[i], _anharmonicities[i], _AC_stark_detunings[i], _x90_lens[i], -_x90_amplitudes[i])
    y90_I_wf, y90_Q_wf, _y90_len, _y90_amp = generate_drag_y180(_drag_coefficients[i], _anharmonicities[i], _AC_stark_detunings[i], _x90_lens[i], _x90_amplitudes[i])
    y180_I_wf, y180_Q_wf, _y180_len, _y180_amp = generate_drag_y180(_drag_coefficients[i], _anharmonicities[i], _AC_stark_detunings[i], _x180_lens[i], _x180_amplitudes[i])
    minus_y90_I_wf, minus_y90_Q_wf, _minus_y90_len, _minus_y90_amp = generate_drag_minus_y90(_drag_coefficients[i], _anharmonicities[i], _AC_stark_detunings[i], _x90_lens[i], -_x90_amplitudes[i])
    qubit_i_pulses = {
        f"x90_pulse_{ii}": {
            "operation": "control",
            "length": _x90_len,
            "waveforms": {
                "I": f"x90_I_wf_{ii}",
                "Q": f"x90_Q_wf_{ii}",
            },
        },
        f"x180_pulse_{ii}": {
            "operation": "control",
            "length": _x180_len,
            "waveforms": {
                "I": f"x180_I_wf_{ii}",
                "Q": f"x180_Q_wf_{ii}",
            },
        },
        f"-x90_pulse_{ii}": {
            "operation": "control",
            "length": _minus_x90_len,
            "waveforms": {
                "I": f"-x90_I_wf_{ii}",
                "Q": f"-x90_Q_wf_{ii}",
            },
        },
        f"y90_pulse_{ii}": {
            "operation": "control",
            "length": _y90_len,
            "waveforms": {
                "I": f"y90_I_wf_{ii}",
                "Q": f"y90_Q_wf_{ii}",
            },
        },
        f"y180_pulse_{ii}": {
            "operation": "control",
            "length": _y180_len,
            "waveforms": {
                "I": f"y180_I_wf_{ii}",
                "Q": f"y180_Q_wf_{ii}",
            },
        },
        f"-y90_pulse_{ii}": {
            "operation": "control",
            "length": _minus_y90_len,
            "waveforms": {
                "I": f"-y90_I_wf_{ii}",
                "Q": f"-y90_Q_wf_{ii}",
            },
        },
    }
    qubit_pulses = {**qubit_pulses, **qubit_i_pulses}
    qubit_i_waveforms = {
        f"x90_I_wf_{ii}": {"type": "arbitrary", "samples": x90_I_wf.tolist()},
        f"x90_Q_wf_{ii}": {"type": "arbitrary", "samples": x90_Q_wf.tolist()},
        f"x180_I_wf_{ii}": {"type": "arbitrary", "samples": x180_I_wf.tolist()},
        f"x180_Q_wf_{ii}": {"type": "arbitrary", "samples": x180_Q_wf.tolist()},
        f"-x90_I_wf_{ii}": {"type": "arbitrary", "samples": minus_x90_I_wf.tolist()},
        f"-x90_Q_wf_{ii}": {"type": "arbitrary", "samples": minus_x90_Q_wf.tolist()},
        f"y90_I_wf_{ii}": {"type": "arbitrary", "samples": y90_I_wf.tolist()},
        f"y90_Q_wf_{ii}": {"type": "arbitrary", "samples": y90_Q_wf.tolist()},
        f"y180_I_wf_{ii}": {"type": "arbitrary", "samples": y180_I_wf.tolist()},
        f"y180_Q_wf_{ii}": {"type": "arbitrary", "samples": y180_Q_wf.tolist()},
        f"-y90_I_wf_{ii}": {"type": "arbitrary", "samples": minus_y90_I_wf.tolist()},
        f"-y90_Q_wf_{ii}": {"type": "arbitrary", "samples": minus_y90_Q_wf.tolist()},
    }
    qubit_waveforms  = {**qubit_waveforms, **qubit_i_waveforms}
qubit_pulses = {
    **qubit_pulses,
    "pi_pulse": {
        "operation": "control",
        "length": square_pi_len,
        "waveforms": {
            "I": "pi_wf",
            "Q": "zero_wf",
        },
    },
    "pi_half_pulse": {
        "operation": "control",
        "length": square_pi_len,
        "waveforms": {
            "I": "pi_half_wf",
            "Q": "zero_wf",
        },
    },
}
qubit_waveforms = {
    **qubit_waveforms, 
    "pi_wf": {"type": "constant", "sample": square_pi_amp},
    "pi_half_wf": {"type": "constant", "sample": square_pi_amp / 2},
}

#%% ---- Create dictionary to parse parameters for multiplexed readout ---- #
multiplexed_parameters = {}
for i, key in enumerate(_qubit_keys):
    multiplexed_parameters[key] = {
        "qubit_key": _qubit_keys[i],
        "resonator_key": _resonator_keys[i],
        "readout_len": _readout_lens[i],
        "readout_amp": _readout_amplitudes[i],
        "rotation_angle": _rotation_angles[i],
        "ge_threshold": _ge_thresholds[i],
        "resonator_frequency": _resonator_frequency[i],
        "resonator_IF": _resonator_IF[i],
        "resonator_LO": _resonator_LO,
        "qubit_frequency": _qubit_frequency[i],
        "qubit_IF": _qubit_IF[i],
        "qubit_LO": _qubit_LO[i],
        "qubit_relaxation": _qubit_relaxation_times[i],
        "control_amp": _control_amp[i],
        "drag_coef": _drag_coefficients[i],
        "anharmonicity": _anharmonicities[i],
        "resonator_relaxation": _resonator_relaxation_times[i],
        "x180_len": _x180_lens[i],
        "x180_amp": _x180_amplitudes[i],
        "x180_sigma": _x180_lens[i] / 5,
        "x90_len": _x90_lens[i],
        "x90_amp": _x90_amplitudes[i],
        # Flux line parameters
        "flux_key": _flux_keys[i],
        "max_frequency_point": _max_frequency_points[i],
        "flux_settle_time": _flux_settle_times[i],
        "const_flux_len": _const_flux_lens[i],
        "const_flux_amp": _const_flux_amps[i],
        "amplitude_fit": _amplitude_fits[i],
        "frequency_fit": _frequency_fits[i],
        "phase_fit": _phase_fits[i],
        "offset_fit": _offset_fits[i],
    }


# %% Extra definitions
# For detault control pulses
drag_coef_default = 0
anharmonicity_default = -150 * u.MHz
AC_stark_detuning_default = 0 * u.MHz
x180_len_default = 40
x180_amp_default = 1.0

#########################################
# %% ---- Flux elements & pulses ---- #
#########################################
flux_elements = {}
flux_pulses = {}
flux_waveforms = {}
for i, key in enumerate(_flux_keys):
    ii = i + 1
    flux_elements[key] = {
        "singleInput": {
            "port": (con, lf_fem, ii),
        },
        "operations": {
            "const": f"const_flux_pulse_{ii}",
        },
    }
    flux_pulses[f"const_flux_pulse_{ii}"] = {
        "operation": "control",
        "length": _const_flux_lens[i],
        "waveforms": {
            "single": f"const_flux_wf_{ii}",
        },
    }
    flux_waveforms[f"const_flux_wf_{ii}"] = {"type": "constant", "sample": _const_flux_amps[i]}

# Build LF-FEM analog outputs dict
_lf_fem_analog_outputs = {}
for i in range(num_qubits):
    _lf_fem_analog_outputs[i + 1] = {
        "offset": _max_frequency_points[i],
        "output_mode": "amplified",
        "sampling_rate": sampling_rate,
        "upsampling_mode": "pulse",
        # Synchronize LF-FEM with MW-FEM (band 1 & 3 → 141 ns delay, band 2 → 161 ns delay)
        "delay": 141,
    }

_mw_fem_analog_outputs = {}
for i in range(num_qubits):
    _mw_fem_analog_outputs[qubit_analogOutput[i][2]] = {
        "band":qubit_LO_band[i],
        "full_scale_power_dbm":qubit_power[i],
        "upconverters":{
            1:{"frequency":_qubit_LO[i]},
        },
    }

# %% ---- Config ---- #
config = {
    "controllers":{
        con:{
            "type":"opx1000",
            "fems":{
                # declaring MW-FEM for qubit control and resonator readout
                mw_fem: {
                    "type":"MW",
                    "analog_outputs":{ 
                        resonator_analogOutput[2]:{
                            "band":resonator_LO_band,
                            "full_scale_power_dbm":resonator_power,
                            "upconverters":{
                                1:{"frequency":_resonator_LO},
                            },
                        },  # Resonators
                        **_mw_fem_analog_outputs
                    },
                    "analog_inputs":{
                        resonator_analogInput[2]:{
                            "band":resonator_LO_band, 
                            "downconverter_frequency":_resonator_LO,
                            "gain_db": 32,
                        }, # resonator in
                    },
                    "digital_outputs":{ 
                        1: {}, # marker for readout pulse
                    },
                },
                lf_fem: {
                    "type": "LF",
                    "analog_outputs": _lf_fem_analog_outputs,
                    "digital_outputs": {},
                },
            }
        }
    },
    "elements":{
        **qubit_elements,
        **resonator_elements,
        **flux_elements,
    }, 
    "pulses":{
        "const_pulse": {
            "operation": "control",
            "length": const_len,
            "waveforms": {
                "I": "const_wf",
                "Q": "zero_wf",
            },
        },
        "saturation_pulse":{
            "operation":"control",
            "length":saturation_len,
            "waveforms":{
                "I":"saturation_wf",
                "Q":"zero_wf",
            },
        },
        **readout_pulses,
        **qubit_pulses,
        **flux_pulses,
    },
    "waveforms": {
        "const_wf": {"type": "constant", "sample": const_amp},
        "saturation_wf": {"type": "constant", "sample": saturation_amp},
        "zero_wf": {"type": "constant", "sample": 0.0},
        **readout_waveforms,
        **qubit_waveforms,
        **flux_waveforms,
    },
    "digital_waveforms": {
        "ON": {"samples": [(1, 0)]},
    },
    "integration_weights":{
        **readout_integration_weights,
    },
}