import logging

from core.sentinel.config import SentinelConfig, SentryConfig
from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import Initial
from sm.general.phases.pump_vc import IdleVacuum, PumpVC, IdleEvacuateDRUnit
from sm.general.phases.vent_vc import VentVacuum
from sm.general.sentry_rules import sentry_heaters_off, sentry_vent_valve_low_temperature, sentry_vent_valve_room_temperature
from sm.general.sentinel_rules import general_sentinel_rules, magnet_rules
from sm.helium_systems.condensing_1K import (
    Condensing,
    IdleCirculating,
)
from sm.helium_systems.ppc_1K import IdleFourKelvin, StartCirculation
from sm.helium_systems.pt_cooling1K import InitialCooling, PulseTubeCoolingFallbackHelium
from sm.helium_systems.sentinel_rules import pressure_difference_too_high_ln2trap, pressure_p3_high, pressure_p4_high
from sm.helium_systems.warmup_1K import (
    CollectMixture,
    IdleWarm,
    StopCooling,
    WaitUntilWarm,
    CollectMixtureInitial,
)
from sm.helium_systems.parameters import helium_parameters

#pressure_p4_high_placeholder, opening_v102


logger = logging.getLogger(__name__)


config = StateMachineConfig(
    name="helium-systems",
    transitions=(
        # Pump Vacuum Can
        (IdleWarm, VentVacuum),
        (VentVacuum, IdleWarm),
        (IdleWarm, PumpVC),
        (Initial, PumpVC),
        (PumpVC, IdleVacuum),
        (IdleWarm,IdleEvacuateDRUnit),
        (IdleEvacuateDRUnit,PumpVC),

        # Pulse Tube Cooling
        (IdleVacuum, InitialCooling),
        (InitialCooling, StartCirculation),

        # Pulse Pre Cooling
        (StartCirculation, IdleFourKelvin),

        # Condensing
        (IdleFourKelvin, Condensing),
        (Condensing, IdleCirculating),

        # Warmup
        (IdleCirculating, CollectMixtureInitial),
        (CollectMixtureInitial, IdleFourKelvin),
        (IdleCirculating, StopCooling),
        (StopCooling, CollectMixture),
        #(CollectMixture, StopPumping),
        (CollectMixture, WaitUntilWarm),
        (WaitUntilWarm, IdleWarm),

        # transitions to enable stopping operations
        (PumpVC, IdleWarm),
        (IdleEvacuateDRUnit,IdleWarm),
        (IdleVacuum, IdleWarm),
        (InitialCooling, WaitUntilWarm),
        (IdleFourKelvin, StopCooling),
        (Condensing, StopCooling),
    ),
    parameter_mapping=helium_parameters,
    recovery_paths= [(PulseTubeCoolingFallbackHelium, IdleCirculating)]
)


sentinel = SentinelConfig(
    [
        pressure_difference_too_high_ln2trap,
        pressure_p3_high,
        pressure_p4_high,
    ] + general_sentinel_rules
    + magnet_rules
)


sentry = SentryConfig([sentry_heaters_off, sentry_vent_valve_low_temperature, sentry_vent_valve_room_temperature])
