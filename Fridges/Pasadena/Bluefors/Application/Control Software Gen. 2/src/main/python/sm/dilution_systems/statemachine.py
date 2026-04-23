import logging

from core.sentinel.config import SentinelConfig, SentryConfig
from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import Initial
from sm.dilution_systems.parameters import parameters
from sm.general.sentry_rules import sentry_heaters_off, sentry_vent_valve_low_temperature, sentry_vent_valve_room_temperature
from sm.general.sentinel_rules import general_sentinel_rules, magnet_rules
from sm.dilution_systems.sentinel_rules import (
    pressure_difference_too_high_ln2trap,
    pressure_p3_high,
    pressure_p4_high,
    mixing_chamber_heater_power_too_high,
    still_heater_power_too_high,
)
from sm.general.phases.condensing import (
    Condensing,
    IdleCirculating,
)
from sm.general.phases.ppc import (
    IdleFourKelvin,
    PulsePreCooling,
)
from sm.general.phases.pt_cooling import (
    PulseTubeCoolingFallback,
    PulseTubeCoolingFinalizationWithoutPPC,
    InitialCooling,
)
from sm.general.phases.pump_vc import IdleVacuum, PumpVC, IdleEvacuateDRUnit
# from sm.general.phases.test import TestProcedure
from sm.general.phases.vent_vc import VentVacuum
from sm.general.phases.warmup import (
    CollectMixtureInitial,
    IdleWarm,
    WaitUntilWarm,
    StopCoolingCollectMixture
)

# pressure_p4_high_placeholder, opening_v102


logger = logging.getLogger(__name__)


config = StateMachineConfig(
    name="Dilution State Machine",
    transitions=(
        # (Initial, TestProcedure),
        # Pump Vacuum Can
        (IdleWarm, VentVacuum),
        (VentVacuum, IdleWarm),
        (Initial, PumpVC),
        (IdleWarm, PumpVC),
        (PumpVC, IdleVacuum),
        (IdleWarm,IdleEvacuateDRUnit),
        (IdleEvacuateDRUnit,PumpVC),
        # Pulse Tube Cooling
        (IdleVacuum, InitialCooling),
        (InitialCooling, PulseTubeCoolingFinalizationWithoutPPC),
        (PulseTubeCoolingFinalizationWithoutPPC, IdleFourKelvin),
        # Pulse Pre Cooling
        (InitialCooling, PulsePreCooling),
        (PulsePreCooling, IdleFourKelvin),
        # Condensing
        (IdleFourKelvin, Condensing),
        (Condensing, IdleCirculating),
        # Warmup
        (IdleCirculating, CollectMixtureInitial),
        (CollectMixtureInitial, IdleFourKelvin),
        (IdleFourKelvin,StopCoolingCollectMixture),
        (IdleCirculating,StopCoolingCollectMixture),
        (StopCoolingCollectMixture,WaitUntilWarm),
        (WaitUntilWarm, IdleWarm),
        # transitions to enable stopping operations
        (PumpVC, IdleWarm),
        (IdleVacuum, IdleWarm),
        (IdleEvacuateDRUnit,IdleWarm),
        (InitialCooling, WaitUntilWarm),
        (PulseTubeCoolingFinalizationWithoutPPC, WaitUntilWarm),
        (Condensing, StopCoolingCollectMixture),
    ),
    parameter_mapping=parameters,
    recovery_paths= [(PulseTubeCoolingFallback, IdleCirculating)]
)


sentinel = SentinelConfig(
    [
        pressure_difference_too_high_ln2trap,
        pressure_p3_high,
        pressure_p4_high,
        #mixing_chamber_heater_power_too_high,
        #still_heater_power_too_high,
    ] + general_sentinel_rules
    + magnet_rules,
    sentinel_parameters={"still_heating_power_limit": 0.1}
)


sentry = SentryConfig([sentry_heaters_off, sentry_vent_valve_low_temperature, sentry_vent_valve_room_temperature])
