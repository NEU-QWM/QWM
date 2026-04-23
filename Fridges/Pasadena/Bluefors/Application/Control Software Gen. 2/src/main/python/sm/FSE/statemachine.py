import logging

import core.api
from core.device.command import AlertCommand, AlertSeverity
from core.sentinel.config import SentinelConfig, SentryConfig
from sm.general.sentry_rules import sentry_heaters_off, sentry_vent_valve_low_temperature, sentry_vent_valve_room_temperature
from sm.general.sentinel_rules import general_sentinel_rules, magnet_rules
from sm.FSE.sentinel_rules import (
    pressure_difference_too_high_ln2trap,
    pressure_p3_high,
    pressure_p4_high,
    mixing_chamber_heater_power_too_high,
    still_heater_power_too_high,
)


from core.state_machine.config import StateMachineConfig
from core.state_machine.procedure import Initial, Procedure
from sm.FSE.parameters import parameters
from sm.general.phases.condensing import (
  IdleCirculating,
)
from sm.general.phases.FSE import (
  RemoveFSECold,
  InsertFSECold,
  InsertFSEWarm,
  RemoveFSEWarm,
  PumpFSEBellowCold,
  PulseTubeCoolingFallbackFSE,
  PumpVCandFSE,
  PumpVCInsertFSEWarm,
)
from sm.general.phases.ppc import (
  EvacuateDilutionRefrigerator,
  IdleFourKelvin,
  PulsePreCooling,
)
from sm.general.phases.pt_cooling import (
  PulseTubeCoolingFinalizationWithoutPPC,
  InitialCooling
)
from sm.general.phases.pump_vc import IdleVacuum, PumpVC, IdleEvacuateDRUnit
from sm.general.phases.vent_vc import VentVacuum
from sm.general.phases.warmup import (
  IdleWarm,
  WaitUntilWarm,
  StopCoolingCollectMixture
)
from sm.dilution_systems.sentinel_rules import (
  pressure_difference_too_high_ln2trap,
  pressure_p3_high,
  pressure_p4_high,
)

logger = logging.getLogger(__name__)

class LoopTest(Procedure):
    name = "FSE loop test"

    # def validate(self, parameters):
    #   pass

    def procedure(self, parameters):
        core.api.alert(AlertCommand(AlertSeverity.INFO, 1649, "Hi from loop procedure", "Automation notification"))
        self.wait(3)



config = StateMachineConfig(
    name="FSE State Machine",
    transitions=(
      # Pump Vacuum Can
      (IdleWarm, VentVacuum),
      (VentVacuum, IdleWarm),
      (Initial, PumpVC),
      (PumpVC, IdleVacuum),
      (PumpVC, InitialCooling),
      (IdleWarm,IdleEvacuateDRUnit),
      (IdleEvacuateDRUnit,PumpVC),
      (IdleEvacuateDRUnit,PumpVCandFSE),
      (IdleEvacuateDRUnit,PumpVCInsertFSEWarm),
      (IdleWarm, PumpVCInsertFSEWarm),
      (PumpVCInsertFSEWarm, IdleVacuum),
      (Initial,PumpVCandFSE),
      (IdleWarm,PumpVCandFSE),
      (PumpVCandFSE, IdleVacuum),
      # Pulse Tube Cooling
      (IdleVacuum, InitialCooling),
      # Pulse Pre Cooling
      (InitialCooling, PulseTubeCoolingFinalizationWithoutPPC),
      (PulseTubeCoolingFinalizationWithoutPPC, IdleFourKelvin),
      (InitialCooling, PulsePreCooling),
      (PulsePreCooling, IdleFourKelvin),
      (IdleFourKelvin,PumpFSEBellowCold),
      (PumpFSEBellowCold,InsertFSECold),
      (InsertFSECold,IdleCirculating),

      # Warmup

      (IdleCirculating,RemoveFSECold),
      (RemoveFSECold,IdleFourKelvin),
      (IdleEvacuateDRUnit,IdleWarm),
      (IdleFourKelvin,StopCoolingCollectMixture),
      (IdleCirculating,StopCoolingCollectMixture),
      (StopCoolingCollectMixture,WaitUntilWarm),
      (WaitUntilWarm, IdleWarm),
      (IdleWarm, PumpVC),  # Make it possible to start another cooldown
      # transitions to enable stopping operations
      (PumpVC, IdleWarm),
      (PumpVCandFSE, IdleWarm),
      (PumpVCInsertFSEWarm, IdleWarm),
    ),
    parameter_mapping=parameters,
    recovery_paths= [(PulseTubeCoolingFallbackFSE, IdleCirculating)],
    loop_procedures={
      IdleVacuum: [(InsertFSEWarm,),(RemoveFSEWarm,),],
                    }
)


# TODO: Should the FSE Sentry/Sentinel be identical to dilution-systems?
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