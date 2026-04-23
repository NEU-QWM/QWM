from enum import Enum


class SystemType(Enum):
    PYTHON_TEST = "python-test"
    IT = "IT"
    CS2_GHS = "CS2-GHS"
    GHS_250 = "GHS-250"
    GHS_400 = "GHS-400"
    GHS_1000 = "GHS-1000"
    GHS_1000_FSE = "GHS-1000-FSE"


# Overrides the parameters from sm/*/statemachine.py SentinelConfig
sentinel_parameters = {
    SystemType.PYTHON_TEST: {},
    SystemType.IT: {},
    SystemType.CS2_GHS: {},
    SystemType.GHS_250: {"still_heating_power_limit": 0.1},
    SystemType.GHS_400: {},
    SystemType.GHS_1000: {},
    SystemType.GHS_1000_FSE: {},
}
