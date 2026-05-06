from qm.qua import *
import numpy as np

def single_qubit_parser(multiplexed_parameters, qubit_key, call_list=None):
    '''
    Parse multiplexed parameters for the given qubit key. Returns Tuple of single values for the qubit key.
    If call_list is given, returns only the parameters in the call_list in the order they are given.

    :param multiplexed_parameters: Dictionary of the multiplexed parameters for all qubits (taken from configuration file).
    :param qubit_key: Qubit key to parse the parameters for. 
    :param call_list: List of parameter names to return. If None, returns large subset of parameters (in order specified below). Keys available: ['qubit_key', 'resonator_key', 'readout_len', 'readout_amp', 'rotation_angle', 'ge_threshold', 'resonator_frequency', 'resonator_IF', 'resonator_LO', 'qubit_frequency', 'qubit_IF', 'qubit_LO', 'qubit_relaxation', 'drag_coef', 'anharmonicity', 'resonator_relaxation', 'x180_len', 'x180_amp', 'x90_len', 'x90_amp']
    :return: Tuple of single values in the order specified in call_list. (default order is: "qubit_key", "qubit_frequency", "qubit_LO", "qubit_IF","resonator_key", "resonator_frequency", "resonator_LO", "resonator_IF", "readout_len", "qubit_relaxation", "resonator_relaxation", "ge_threshold", "drag_coef", "anharmonicity")
    '''
    if call_list is None:
        call_list = ["qubit_key", "qubit_frequency", "qubit_LO", "qubit_IF", "resonator_key", "resonator_frequency", "resonator_LO", "resonator_IF", "readout_len", "qubit_relaxation", "resonator_relaxation", "ge_threshold", "drag_coef", "anharmonicity"]
    list_to_return = []
    for item in call_list:
        list_to_return.append(multiplexed_parameters[qubit_key][item])
    return tuple(list_to_return)

def multiplexed_parser(multiplexed_parameters, qubit_keys = None, resonator_keys = None, call_list=None):
    '''
    Parse multiplexed parameters for the given qubit keys. Returns Tuple of arrays of the parameters in order of the qubit keys given.
    If call_list is given, returns only the parameters in the call_list in the order they are given.

    :param multiplexed_parameters: Dictionary of the multiplexed parameters for all qubits (taken from configuration file).
    :param qubit_keys: List of qubit keys to parse the parameters for. If given, will override qubit_keys and only parse resonator parameters.
    :param resonator_keys: List of resonator keys to parse the parameters for. 
    :param call_list: List of parameter names to return. If None, returns large subset of parameters (in order specified below). Keys available: ['qubit_key', 'resonator_key', 'readout_len', 'readout_amp', 'rotation_angle', 'ge_threshold', 'resonator_frequency', 'resonator_IF', 'resonator_LO', 'qubit_frequency', 'qubit_IF', 'qubit_LO', 'qubit_relaxation', 'drag_coef', 'anharmonicity', 'resonator_relaxation', 'x180_len', 'x180_amp', 'x90_len', 'x90_amp']
    :return: Tuple of lists/arrays of the parameters in order of the qubit keys given, or in the order specified in call_list. (default order is: "qubit_key", "qubit_frequency", "qubit_LO", "qubit_IF","resonator_key", "resonator_frequency", "resonator_LO", "resonator_IF", "readout_len", "qubit_relaxation", "resonator_relaxation", "ge_threshold", "drag_coef", "anharmonicity")
    '''
    if qubit_keys is None:
        if resonator_keys is None:
            raise ValueError("Either qubit_keys or resonator_keys must be provided.")
        else:
            qubit_keys = []
            for key in multiplexed_parameters:
                if multiplexed_parameters[key]["resonator_key"] in resonator_keys:
                    qubit_keys.append(key)
    if call_list is None:
        call_list = ["qubit_key", "qubit_frequency", "qubit_LO", "qubit_IF", "resonator_key", "resonator_frequency", "resonator_LO", "resonator_IF", "readout_len", "qubit_relaxation", "resonator_relaxation", "ge_threshold", "drag_coef", "anharmonicity"]
    list_to_return = []
    for item in call_list:
        item_list = []
        for key in qubit_keys:
            if key in list(multiplexed_parameters.keys()):
                item_list.append(multiplexed_parameters[key][item])
        list_to_return.append(np.array(item_list))
    return tuple(list_to_return)

##############
# QUA macros #
##############

def reset_qubit(qubit, resonator, method, **kwargs):
    """
    Macro to reset the qubit state.

    If method is 'cooldown', then the variable cooldown_time (in clock cycles) must be provided as a python integer > 4.

    **Example**: reset_qubit('cooldown', cooldown_times=500)

    If method is 'active', then 3 parameters are available as listed below.

    **Example**: reset_qubit('active', threshold=-0.003, max_tries=3)

    :param qubit: Qubit name as in the config file.
    :param resonator: Resonator name as in the config file.
    :param method: Method the reset the qubit state. Can be either 'cooldown' or 'active'.
    :type method: str
    :key cooldown_time: qubit relaxation time in clock cycle, needed if method is 'cooldown'. Must be an integer > 4.
    :key threshold: threshold to discriminate between the ground and excited state, needed if method is 'active'.
    :key max_tries: python integer for the maximum number of tries used to perform active reset,
        needed if method is 'active'. Must be an integer > 0 and default value is 1.
    :key Ig: A QUA variable for the information in the `I` quadrature used for active reset. If not given, a new
        variable will be created. Must be of type `Fixed`.
    :return:
    """
    if method == "cooldown":
        # Check cooldown_time
        cooldown_time = kwargs.get("cooldown_time", None)
        if (cooldown_time is None) or (cooldown_time < 4):
            raise Exception("'cooldown_time' must be an integer > 4 clock cycles")
        # Reset qubit state
        wait(cooldown_time, qubit)
    elif method == "active":
        # Check threshold
        threshold = kwargs.get("threshold", None)
        if threshold is None:
            raise Exception("'threshold' must be specified for active reset.")
        # Check max_tries
        max_tries = kwargs.get("max_tries", 1)
        if (max_tries is None) or (not float(max_tries).is_integer()) or (max_tries < 1):
            raise Exception("'max_tries' must be an integer > 0.")
        # Check Ig
        Ig = kwargs.get("Ig", None)
        # Reset qubit state
        return active_reset(qubit, resonator, threshold, max_tries=max_tries, Ig=Ig)


# Macro for performing active reset until successful for a given number of tries.
def active_reset(qubit, resonator, threshold, max_tries=1, Ig=None):
    """Macro for performing active reset until successful for a given number of tries.

    :param qubit: Qubit name as in the config file.
    :param resonator: Resonator name as in the config file.
    :param threshold: threshold for the 'I' quadrature discriminating between ground and excited state.
    :param max_tries: python integer for the maximum number of tries used to perform active reset. Must >= 1.
    :param Ig: A QUA variable for the information in the `I` quadrature. Should be of type `Fixed`. If not given, a new
        variable will be created
    :return: A QUA variable for the information in the `I` quadrature and the number of tries after success.
    """
    if Ig is None:
        Ig = declare(fixed)
    if (max_tries < 1) or (not float(max_tries).is_integer()):
        raise Exception("max_count must be an integer >= 1.")
    # Initialize Ig to be > threshold
    assign(Ig, threshold + 2**-28)
    # Number of tries for active reset
    counter = declare(int)
    # Reset the number of tries
    assign(counter, 0)

    # Perform active feedback
    align(qubit, resonator)
    # Use a while loop and counter for other protocols and tests
    with while_((Ig > threshold) & (counter < max_tries)):
        # Measure the resonator
        measure(
            "readout",
            resonator,
            dual_demod.full("opt_cos", "opt_sin", Ig),
        )
        # Play a pi pulse to get back to the ground state
        play("pi", qubit, condition=(Ig > threshold))
        # Increment the number of tries
        assign(counter, counter + 1)
    return Ig, counter


# Single shot readout macro
def readout_macro(resonator=None, threshold=None, state=None, I=None, Q=None):
    """
    A macro for performing the readout, with the ability to perform state discrimination.
    If `threshold` is given, the information in the `I` quadrature will be compared against the threshold and `state`
    would be `True` if `I > threshold`.
    Note that it is assumed that the results are rotated such that all the information is in the `I` quadrature.

    :param threshold: Optional. The threshold to compare `I` against.
    :param state: A QUA variable for the state information, only used when a threshold is given.
        Should be of type `bool`. If not given, a new variable will be created
    :param I: A QUA variable for the information in the `I` quadrature. Should be of type `Fixed`. If not given, a new
        variable will be created
    :param Q: A QUA variable for the information in the `Q` quadrature. Should be of type `Fixed`. If not given, a new
        variable will be created
    :return: Three QUA variables populated with the results of the readout: (`state`, `I`, `Q`)
    """
    if I is None:
        I = declare(fixed)
    if Q is None:
        Q = declare(fixed)
    if threshold is not None and state is None:
        state = declare(bool)
    measure(
        "readout",
        resonator,
        dual_demod.full("opt_cos", "opt_sin", I),
        dual_demod.full("opt_minus_sin", "opt_cos", Q),
    )
    if threshold is not None:
        assign(state, I > threshold)
    return state, I, Q


def ge_averaged_measurement(qubit, resonator, cooldown_time, n_avg):
    """Macro measuring the qubit's ground and excited states n_avg times for Bloch vector calibration.
    The averaged I and Q quadratures can be retrieved via stream processing (Ig_st.average().save("Ig")).

    :param qubit: Qubit element name as in the config file.
    :param resonator: Resonator element name as in the config file.
    :param cooldown_time: Cooldown time between measurements in clock cycles (4ns units).
    :param n_avg: Number of averaging iterations (Python integer).
    :return: Streams for I and Q data for ground and excited states: [Ig_st, Qg_st, Ie_st, Qe_st].
    """
    n = declare(int)
    I = declare(fixed)
    Q = declare(fixed)
    Ig_st = declare_stream()
    Qg_st = declare_stream()
    Ie_st = declare_stream()
    Qe_st = declare_stream()
    with for_(n, 0, n < n_avg, n + 1):
        # Ground state calibration
        align(qubit, resonator)
        measure(
            "readout",
            resonator,
            dual_demod.full("cos", "sin", I),
            dual_demod.full("minus_sin", "cos", Q),
        )
        wait(cooldown_time, resonator, qubit)
        save(I, Ig_st)
        save(Q, Qg_st)
        # Excited state calibration
        align(qubit, resonator)
        play("x180", qubit)
        align(qubit, resonator)
        measure(
            "readout",
            resonator,
            dual_demod.full("cos", "sin", I),
            dual_demod.full("minus_sin", "cos", Q),
        )
        wait(cooldown_time, resonator, qubit)
        save(I, Ie_st)
        save(Q, Qe_st)
    return Ig_st, Qg_st, Ie_st, Qe_st
