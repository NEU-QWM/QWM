import logging
from datetime import timedelta

from core.api import state
from core.device import device
from core.state_machine.procedure import Direction, Procedure
from core.state_machine.exceptions import ProcedureError, ValidationError
from sm.general.helpers import Helpers

logger = logging.getLogger(__name__)


class StopVacuumPumping(Procedure):
    name = "Stop pumping vacuum can"
    image_url = "images/Pulse_Tube.mp4"
    penalty = timedelta(minutes=5)
    required_parameters = [
        "serviceBoosterPumpAvailable",
        "pulseTubeCoolingTargetPressure",
        "vacuumPressureLimit",
        "initialTankPressure",
    ]
    direction = Direction.COOLING

    '''
    Sequence: 
    - Turn off turbo and scroll pump
    - close service manifold valves
    '''

    def enter(self, parameters):
        device.pulse_tube_on("PULSE_TUBE")
        device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

    def validate(self, parameters, state):
        if (
            state["P1_PRESSURE"] > parameters["pulseTubeCoolingTargetPressure"]
            or state["50K_TEMPERATURE"] > 85
            or state["4K_TEMPERATURE"] > 50
            or state["STILL_TEMPERATURE"] > 55
        ):
            yield ValidationError(1649, "System too warm to stop pumping vacuum can")
        # TODO Check if V101 is closed -> procreturnerror
        if state["4K_TEMPERATURE"] < 4.6 or state["STILL_TEMPERATURE"] < 5.3:
            yield ValidationError(1649, "System already at low temperature")
        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")

    def procedure(self, parameters):
        logger.info("StopVacuumPumping: Turning off pumps and valves")

        Helpers.pump_off_turbo(parameters)
        device.pump_off("R2")

        if parameters["serviceBoosterPumpAvailable"]:
            device.valves_off(["V101", "V102", "V104", "V105", "V107", "V106"])
        else:
            device.valves_off(["V101", "V102", "V105", "V112", "V114"])

class InitialCooling(Procedure):
    name="Initial cooling"
    image_url="images/Pulse_Tube.mp4"
    penalty=timedelta(hours=24)
    required_parameters = [
        "pulseTubeCoolingMaxTime",
        "vacuumPressureErrorTolerance",
        "pumpTurboFinalPressure",
        "pulseTubeCoolingTargetPressure",
        "dilutionRefrigeratorEvacuatedPressure",
        "initialTankPressure",
        "serviceBoosterPumpAvailable",
        "vacuumPressureLimit",
        "pulseTubeCoolingFinalTemperature",
    ]
    direction = Direction.COOLING

    '''
    Sequence: 
    - Close circulation valves
    - Turn on scroll pump
    - Open valves depending of service booster pump availability
    - Turn on PTs and heatswitches
    - Wait for P1 < pulseTubeCoolingTargetPressure, 
                    T50K < 85K,
                    T4K < 50K,
                    Tstill < 55K
                    
    - Turn off turbo and scroll pump
    - close service manifold valves
    
    - wait for Tstill and T4K < pulseTubeCoolingFinalTemperature (15K)
    '''

    def validate(self, parameters, state):
        if state["P1_PRESSURE"] > parameters["vacuumPressureErrorTolerance"] * parameters["pumpTurboFinalPressure"]:
            yield ValidationError(1649, "P1 too high to start PT cooling")
        if state["P3_PRESSURE"] > parameters["dilutionRefrigeratorEvacuatedPressure"]:
            yield ValidationError(1649, "P3 pressure too high")
        if "FSE" in state:
            if state["4K_TEMPERATURE"] < 4.6 or state["STILL_TEMPERATURE"] < 6:
                yield ValidationError(1649, "System already at low temperature")
        else:
            if state["4K_TEMPERATURE"] < 4.6 or state["STILL_TEMPERATURE"] < 5.3:
                yield ValidationError(1649, "System already at low temperature")
        if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            yield ValidationError(1649, "P5 pressure below limit, check mixture amount")

    def enter(self, parameters):
        self.command_queue.queue_valves_off(
            [
                "V001",
                "V003",
                "V004",
                "V005",
                "V113",
                "V201G",
                "V202",
                "V203",
                "V303",
                "V306",
                "V401",
                "V402",
                "V403",
                "V404",
                "V405",
                "V406",
                "V407",
                "V501H",
                "V502H",
                "V503H",
            ]
        )


    def procedure(self, parameters):

      if not state["P1_ENABLED"]:
        device.set_cold_cathode("P1")

      # PT Cooling

      logger.info("PT Cooling: PT On: Turning on pulse tubes and heat switches")

      device.pulse_tube_on("PULSE_TUBE")

      # Note that heatswitches are turned on similarly as heaters
      device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

      if (state["P1_PRESSURE"] > parameters["pulseTubeCoolingTargetPressure"]
          or state["50K_TEMPERATURE"] > 85
          or state["4K_TEMPERATURE"] > 50
          or state["STILL_TEMPERATURE"] > 55
      ):
          Helpers.pump_on_turbo(parameters)
          device.pump_on("R2")
          self.command_queue.queue_valves_on(["V204NO", "V205NO", "V206NO"])

          if parameters["serviceBoosterPumpAvailable"]:
              self.command_queue.queue_valves_on(["V101", "V104", "V107", "V106"])
          else:
              self.command_queue.queue_valves_on(["V101", "V112", "V114", "V105"])
          self.command_queue.execute_queued_commands()



      sw = self.stopwatch()
      logger.info("Waiting until T50K< 85K, T4K< 50K, Tstill< 55K and P1< pulseTubeCoolingTargetPressure")
      while (
          state["P1_PRESSURE"] > parameters["pulseTubeCoolingTargetPressure"]
          or state["50K_TEMPERATURE"] > 85
          or state["4K_TEMPERATURE"] > 50
          or state["STILL_TEMPERATURE"] > 55
      ):
        self.wait(5)
        if sw.elapsed > parameters["pulseTubeCoolingMaxTime"]:
          raise ProcedureError(1649, "Maximum time exceeded for pre-cooling")

      # StopVacuumPumping

      logger.info("StopVacuumPumping: Turning off pumps and valves")

      if parameters["serviceBoosterPumpAvailable"]:
        device.valves_off(["V101", "V102", "V104", "V105", "V107", "V106"])
      else:
        device.valves_off(["V101", "V102", "V105", "V112", "V114"])

      Helpers.pump_off_turbo(parameters)
      device.pump_off("R2")

      # PT Finalization

      logger.info("PT Cooling: PT Cooling finalize: Wait for Still to cool to 15 K")

      logger.info("Waiting for the system to cool to the final temperature...")
      while (
          state["STILL_TEMPERATURE"] > parameters["pulseTubeCoolingFinalTemperature"]
          or state["4K_TEMPERATURE"] > parameters["pulseTubeCoolingFinalTemperature"]
      ):
        self.wait(60)

      logger.info("PT Cooling: Ready for next phase")

class PulseTubeCoolingFinalizationWithoutPPC(Procedure):
    name="Pulse tube cooling without PPC"
    image_url="images/Pulse_Tube.mp4"
    penalty=timedelta(hours=12)
    required_parameters = [
                "pulseTubeCoolingTargetPressure",
                "pulseTubeCoolingFinalTemperature",
                "initialTankPressure",
                "pulseTubeCoolingMaxTime",
                "serviceBoosterPumpAvailable"
]
    direction = Direction.COOLING

    '''
    Sequence:
    - Wait until Tstill < 5.3K (6K if FSE system)  and T4K < 4.6 K 
    '''

    def enter(self, parameters):
        if parameters["serviceBoosterPumpAvailable"]:
            device.valves_off(["V101", "V104", "V105", "V107", "V106"])
        else:
            device.valves_off(["V101", "V112", "V114", "V105"])
        self.wait(1)
        Helpers.pump_off_turbo(parameters)
        device.pump_off("R2")

        device.pulse_tube_on("PULSE_TUBE")
        device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

    def validate(self, parameters, state):
        if (
            state["P1_PRESSURE"] > parameters["pulseTubeCoolingTargetPressure"]
            or state["50K_TEMPERATURE"] > 85
            or state["4K_TEMPERATURE"] > parameters["pulseTubeCoolingFinalTemperature"]
            or state["STILL_TEMPERATURE"] > parameters["pulseTubeCoolingFinalTemperature"]
        ):
            yield ValidationError(1649, "System too warm")
        if "FSE" in state:
            if state["4K_TEMPERATURE"] < 4.6 or state["STILL_TEMPERATURE"] < 6:
                yield ValidationError(1649, "System already at low temperature")
        else:
            if state["4K_TEMPERATURE"] < 4.6 or state["STILL_TEMPERATURE"] < 5.3:
                yield ValidationError(1649, "System already at low temperature")
    def procedure(self, parameters):
        logger.info("PT Cooling: PT Cooling finalize: Wait for system to cool down 4 K")

        device.pulse_tube_on("PULSE_TUBE")
        device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

        sw = self.stopwatch()
        logger.info("Waiting for the system to cool to the final temperature...")
        if "FSE" in state:
            while state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 6:
                self.wait(60)
                if sw.elapsed > parameters["pulseTubeCoolingMaxTime"]:
                    raise ProcedureError(1649, "Error: Cooldown too slow")
        else:
            while state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 5.3:
                self.wait(60)
                if sw.elapsed > parameters["pulseTubeCoolingMaxTime"]:
                    raise ProcedureError(1649, "Error: Cooldown too slow")

        logger.info("PT Cooling: Ready for next phase")

class PulseTubeCoolingFallback(Procedure):
    name = "Pulse tube cooling fallback"
    image_url = "images/Pulse_Tube.mp4"
    penalty = timedelta(hours=12)
    required_parameters = [
        "pulseTubeCoolingTargetPressure",
        "pulseTubeCoolingFinalTemperature",
        "initialTankPressure",
        "serviceBoosterPumpAvailable",
        "mixtureCollectingPressureLimit",
        "collectExtraMixtureTimeLimit",
        "p2PressureLimitMixtureInTank",
        "p4PressureLimitMixtureInTank",
        "collectMixtureTimeLimit",
        "tankPressureStabilizationTime",
        "pressureStabilizationSqLimit",
        "tankPressureStabilizationMaxTime",
        "roughPumpingMaxTime",
        "pumpRoughFinalPressure",
        "condensingPressureDropMaxTime",
        "condensingPressureDifferenceMaxTime",
        "stillHeatingPower",
        "vacuumPressureLimit",
        "condensingTriggerHeatswitches",
        "systemBlockedTimer",
        "bypassLN2Trap",

    ]

    '''
    Sequence: 
    - Turn on the PTs and Turn off the heatswitches
    - Pump VC if P1 > "vacuumPressureLimit"
    - Turn on heatswitch if Tmxc or Tstill > T4K
    - Wait for T4K < 4.6 K and Tstill < 5.3 K 
    - High pressure condensing:
    - Turn off heatswitches once P5 < ("initialTankPressure"-0.2)
    - Open valves to initialize circulation, and turn on the circulation pump R1
    - Main loop to condense 
    - stop when P5 < 250 mbar
    - Low pressure condensing:
    - Main condensing loop
    - stop when P5 < 50mbar
    - Finalization condensing:
    - Pump remaining gas into circulation
    - Stop compressor, open the valves of the normal circulation path
    - Wait 20min and turn on still heater
    '''

    direction = Direction.COOLING

    def validate(self, parameters, state):
        if state["50K_TEMPERATURE"] < state["STILL_TEMPERATURE"]:
            yield ValidationError(1649, "Still is warmer than 50K flange")

    def enter(self, parameters):
        device.pulse_tube_on("PULSE_TUBE")
        device.heaters_off(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])
        device.heaters_off(["STILL_HEATER", "MXC_HEATER"])

        # Confirm that these valves are open or close
        self.command_queue.queue_valves_off(["V101", "V102", "104", "V105", "V106", "V107", "V108",
                           "V109", "V110", "V111", "V112", "V113", "V114", "V303",
                           "V306","V404", "V406", "V501H", "V503H"])

        if state['V201G_ENABLED'] == False:
            device.valves_on(['V202'])
            self.wait(5)
            device.valves_on(['V201G'])
            self.wait(1)
            device.valves_off(['V202'])
        self.command_queue.queue_valves_off(["V003", "V004", "V202", "V203"])
        self.command_queue.queue_valves_on(["V001", "V005", "V302", "V304",
                                            "V502H", "V504H",
                                            "V204NO", "V205NO", "V206NO"])
        self.command_queue.queue_pumps_off(["COM"])
        Helpers.pump_on_circulation_pump_R1(parameters)
        logger.info("System in safe circulation mode")
        Helpers.pump_off_circulation_booster()

    def procedure(self, parameters):
        logger.info("PT Cooling: PT Cooling fallback: Wait for system to cool down 4 K")

        device.pulse_tube_on("PULSE_TUBE")
        device.heaters_off(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

        if state["P1_PRESSURE"] > parameters["vacuumPressureLimit"]:
            if parameters["serviceBoosterPumpAvailable"]:
                logger.info("P1 pressure too high. Pump VC with B2")
                self.pumpVacuumCanWithB2(parameters)
            else:
                logger.info("P1 pressure too high. Collect the mixture")
                self.collectMixture(parameters)

                logger.info("Pump VC with B1")
                self.pumpVacuumCanWithB1(parameters)

        sw = self.stopwatch()
        logger.info("Waiting for the system to cool to the final temperature...")
        while state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 5.3:
            if sw.elapsed > 43200:  # 12 hours
                raise ProcedureError(1649, "Cooldown to 4K exceeds time limit")
            if state["4K_TEMPERATURE"] < state["STILL_TEMPERATURE"]:
                device.heaters_on(["HEATSWITCH_STILL"])
                device.heaters_on(["HEATSWITCH_MXC"])
            self.wait(60)

        logger.info("Start condensing procedure")
        Helpers.pump_off_circulation_booster()
        self.initialize_condensing(parameters)

        # CondensingHighPressure
        if state["P5_PRESSURE"] > 0.250:
            logger.info('Start Condensing High Pressure')

            heat_switch_trigger_pressure = state["P5_PRESSURE"] - parameters["condensingTriggerHeatswitches"]

            sw_high_pressure = self.stopwatch()
            while state["P5_PRESSURE"] > 0.250:
                self.iterate_condensing_high_pressure_loop(parameters, heat_switch_trigger_pressure)
                if sw_high_pressure.elapsed > 18000: # 5h
                    logger.info("Condensing too long")
                    logger.info("Leave system in a safe circulation state")

                    device.valve_off("V003")
                    device.valve_on("V001")

                    device.pump_off("COM")
                    device.valves_off(["V503H", "V003", "V004"])

                    logger.info("Turning on V202, V203, V502H, V005")
                    device.valves_on(["V202", "V203", "V502H", "V005"])

                    self.wait(10)

                    logger.info("Turning off valve V501H")
                    device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture
                    raise ProcedureError(1649, "Condensing timeout during the high pressure sequence")

            device.valve_off("V003")
            device.valve_on("V001")

        else:
            pass

        ## CondensingLowPressure
        device.heater_off("HEATSWITCH_STILL")
        device.heater_off("HEATSWITCH_MXC")
        if state["P5_PRESSURE"] > 0.015:
            while state["P5_PRESSURE"] > 0.050:
                self.iterate_condensing_low_pressure_loop(parameters)

            device.valve_off("V004")
            device.valve_on("V001")
            pass
        else:
            pass

        ## CondensingFinalization
        logger.info("CondensingFinalization: Entering CondensingFinalization")
        self.condensing_finalization(parameters)

        logger.info("Leaving: PulseTubeCoolingFallback")

    def initialize_condensing(self, parameters):
        if state["P5_PRESSURE"] < parameters["initialTankPressure"] - 0.2:
            device.heaters_off(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])
        else:
            device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

        logger.info("Waiting for circulation booster pump to slow down")
        while Helpers.get_circulation_booster_pump_speed() > 150:
            self.wait(15)

        Helpers.close_critical_valves(parameters)

        logger.info("Condensing: Initializing circulation")

        device.valves_on(["V501H", "V503H", "V504H", "V302", "V304"])

        if not parameters["bypassLN2Trap"]:
            device.valves_on(["V401","V402"])
        else:
            device.valves_on(["V403"])

        device.ln2_trap1_led_on("LED_LN2_TRAP")
        device.pumps_on(["COM"])

        device.pumps_on(["R1A"])

        self.wait(10)

        device.valves_on(["V202", "V001"])

        self.wait(60)

        device.valve_on("V201G")
        device.valve_off("V202")

    def iterate_condensing_high_pressure_loop(self, parameters, heat_switch_trigger_pressure):
        """
        Auxiliary method containing the logic for the main loop iterated during CondensingHighPressure.
        Using valves V001 and V003, we first have P4_PRESSURE be over 0.9, and after that wait until it goes below 0.6.
        """
        device.valve_on("V003")
        device.valve_off("V001")

        sw = self.stopwatch()
        while state["P4_PRESSURE"] < 0.900:
            self.wait(0.5)

            if sw.elapsed > 180:
                device.valve_off("V003")
                device.valve_on("V001")

                if state["P5_PRESSURE"] > 0.300:
                    logger.info("Error in condensing: P4 doesn't increase fast enough")
                    logger.info("Leave system in a safe state, recovering mixture")
                    device.pump_off("COM")
                    device.valves_off(["V503H", "V003", "V004", "V403", "V402", "V407"])

                    logger.info("Turning on V202, V203, V502H, V005")
                    device.valves_on(["V202", "V203", "V502H", "V005"])

                    self.wait(10)

                    logger.info("Turning off valve V501H")
                    device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture
                    raise ProcedureError(1649, "Needle valve set too tight, check adjustment")
                else:
                    break

        # Now we are above 900 mbar, so we'll stop mixture intake from the tank

        # Toggle these valves so that P4_PRESSURE is being lowered
        device.valve_off("V003")
        device.valve_on("V001")

        # Reset stopwatch
        sw = self.stopwatch()

        self.wait(10)

        # Evaluate if heat switches can be turned off:
        # TODO if P5 < (initialTankPressure-0.2) close hs-mxc & hs-still
        # TODO refactor procedure
        if (
            state["HEATSWITCH_STILL_ENABLED"]
            and state["HEATSWITCH_MXC_ENABLED"]
            and state["P5_PRESSURE"] < heat_switch_trigger_pressure
        ):
            device.heater_off("HEATSWITCH_MXC")
        # TODO comment out
        if (
            state["HEATSWITCH_STILL_ENABLED"]
            and state["P5_PRESSURE"] < heat_switch_trigger_pressure
            and state["STILL_TEMPERATURE"] < (state["4K_TEMPERATURE"] + 2)
        ):
            device.heater_off("HEATSWITCH_STILL")

        # Then wait for P4_PRESSURE to be under 0.6
        while state["P4_PRESSURE"] > 0.600:
            self.wait(2)

            if sw.elapsed > parameters["systemBlockedTimer"]:  # TODO Verify that this comparison is ok
                # If P4_PRESSURE did not decrease fast enough, raise an error

                logger.info(
                    "CondensingHighPressure — Error: Leave system in a safe state, recovering mixture. "
                    "Turning off COM (helium compressor) and valves V503H, V402, V403, V407"
                )
                device.pump_off("COM")
                device.valves_off(["V503H", "V402", "V403", "V407"])

                logger.info("Condensing: Condensing High P5 — Error: Turning on V202, V203, V502H, V005")
                device.valves_on(["V202", "V203", "V502H", "V005"])

                self.wait(10)

                logger.info("Condensing: Condensing High P5 — Error: Turning off valve V501H")
                device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture

                raise ProcedureError(1649, "System not condensing, check system manual for troubleshooting")

        # If the pressure decreased enough, we can go to the next procedure

    def iterate_condensing_low_pressure_loop(self, parameters):
        """
        Auxiliary method containing the logic for the main loop iterated during CondensingLowPressure.
        Using valves V001 and V004, we first have P4_PRESSURE be over 0.9, and after that wait until it goes below 0.6.
        """
        sw = self.stopwatch()

        device.valve_on("V004")
        device.valve_off("V001")

        # First we wait for P4_PRESSURE to be over 0.9, and we wait for at least 60 seconds
        loop_sw = self.stopwatch()
        while state["P4_PRESSURE"] < 0.900 and loop_sw.elapsed < 60:
            self.wait(0.5)

        # Toggle these valves so that P4_PRESSURE is being lowered again
        device.valve_on("V001")
        device.valve_off("V004")

        self.wait(2)

        # And wait for P4_PRESSURE to be under 0.6
        while state["P4_PRESSURE"] > 0.600:
            self.wait(2)

            if sw.elapsed > parameters["systemBlockedTimer"]:  # TODO Verify that this comparison is ok
                # If P4_PRESSURE did not decrease fast enough, raise an error

                logger.info(
                    "CondensingHighPressure — Error: Leave system in a safe state, recovering mixture. "
                    "Turning off COM (helium compressor) and valves V503H, V402, V407"
                )
                device.pump_off("COM")
                device.valves_off(["V503H", "V402", "V403", "V407"])

                logger.info("Condensing: Condensing High P5 — Error: Turning on V202, V203, V502H, V005")
                device.valves_on(["V202", "V203", "V502H", "V005"])

                self.wait(10)

                logger.info("Condensing: Condensing High P5 — Error: Turning off valve V501H")
                device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture

                raise ProcedureError(1649, "System not condensing, check the system manual for troubleshooting")


    def condensing_finalization(self,parameters):
        logger.info("CondensingFinalization: Tank pressure below 50 mbar, pump remaining gas into circulation")
        device.valve_on("V004")
        self.wait(420) # 7 minutes
        device.valve_off("V004")

        logger.info("CondensingFinalization: Starting normal circulation")
        device.pump_off("COM")

        # Wait for P3_PRESSURE to be under 1.0
        sw = self.stopwatch()
        while state["P3_PRESSURE"] > 1.000:
            self.wait(2)

            if sw.elapsed > parameters["condensingPressureDropMaxTime"]:
                raise ProcedureError(1649, "Condensing pressure not dropping")

        # Wait for P4_PRESSURE to be under P3_PRESSURE
        device.valves_off(["V501H", "V503H"])
        self.wait(2)

        sw = self.stopwatch()
        while state["P4_PRESSURE"] > state["P3_PRESSURE"]:
            self.wait(2)

            if sw.elapsed > parameters["condensingPressureDifferenceMaxTime"]:
                raise ProcedureError(1649, "P3-P4 pressure difference not decreasing")

        # Wait for P3_PRESSURE to drop below 0.9
        logger.info("CondensingFinalization: Wait for P3_PRESSURE to drop below 900 mbar")
        device.valve_on("V502H")
        self.wait(180)

        sw = self.stopwatch()
        while state["P3_PRESSURE"] > 0.900:
            self.wait(5)

            if sw.elapsed > parameters["condensingPressureDropMaxTime"]:
                raise ProcedureError(1649, "P3 pressure not dropping, turbo pump cannot be started")

        Helpers.pump_on_circulation_booster()
        logger.info("CondensingFinalization: Start booster pump")
        self.wait(1200)  # Give time to apply still heat

        device.heater_on("STILL_HEATER")
        device.heater_power("STILL_HEATING_POWER", 3, parameters["stillHeatingPower"])
        logger.info("Apply default Still heater power")
        logger.info("System cooling to base temperature")

    def collectMixture(self, parameters):
        sw = self.stopwatch()
        # Collect mixture
        device.valves_off(["V402", "V403", "V407"])
        device.valves_on(["V005"])

        while (
            state["P3_PRESSURE"] > parameters["mixtureCollectingPressureLimit"]
            and sw.elapsed < parameters["collectExtraMixtureTimeLimit"]
        ):
            # not all collected, continue collecting
            self.wait(30)

        device.valves_on(["V203"])
        device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

        # collect rest of mixture
        logger.info("Collecting the rest of the mixture")

        # check pressures are stabilized
        previous_p5 = state["P5_PRESSURE"]
        logger.info("Wait for checking tank pressure stability")

        sw = self.stopwatch()
        while state["P5_PRESSURE"] < parameters["initialTankPressure"]:
            self.wait(60)
            if sw.elapsed > 36000: # 10 hours
                raise ProcedureError(1649, "Timeout collection of te mixture")

        logger.info("Stop pumping")

        device.valves_off(["V401","V502H", "V203", "V201G", "V001", "V005","V302", "V304"])
        self.wait(10)

        device.valves_off(['V001', 'V003','V004', 'V005',
                           'V101', 'V102', 'V104', 'V105','V106', 'V107', 'V108', 'V109',
                           'V110', 'V111', 'V112', 'V113','V114',
                           'V201G', 'V202', 'V203',
                           'V301','V302','V303','V304','V305','V306',
                           'V401','V402','V403','V404','V405','V406','V407',
                           'V501H','V502H','V503H',
                           'V504H', 'V505H',])

        Helpers.pump_off_circulation_pump_R1(parameters)

    def pumpVacuumCanWithB1(self, parameters):

        device.pumps_on(["R2"])
        Helpers.pump_on_turbo(parameters)
        self.wait(45)
        device.valves_on(["V104", "V105"])
        sw = self.stopwatch()
        while sw.elapsed < parameters["roughPumpingMaxTime"]:
            logger.info("PumpRough manifold in progress, until P6 < pumpRoughFinalPressure")

            if state["P6_PRESSURE"] < parameters["pumpRoughFinalPressure"]:
                return
            else:
                self.wait(10)
        device.valves_off(["V104"])
        device.valves_on(["V112", "V114"])
        sw = self.stopwatch()
        while state["B1A_SPEED"] < 750:  # wait for turbo to ramp up to 750 Hz
            self.wait(10)
            if sw.elapsed > 600:
                raise ProcedureError(1649, "Turbo B1 too long to reach full speed")
        device.valves_on(["V101"])
        sw = self.stopwatch()
        while (
            state["P1_PRESSURE"] > parameters["vacuumPressureLimit"]
            or (state["STILL_TEMPERATURE"] or state["4K_TEMPERATURE"] or state["50K_TEMPERATURE"]) > 70
        ):
            self.wait(10)
            if sw.elapsed > 43200:  # 12 hours:
                raise ProcedureError(1649, "Cooldown to 4K exceed time limit")
        self.wait(300)
        device.valves_off(["V101"])
        self.wait(2)
        device.valves_off(['V001', 'V003','V004', 'V005',
                           'V101', 'V102', 'V104', 'V105','V106', 'V107', 'V108', 'V109',
                           'V110', 'V111', 'V112', 'V113','V114',
                           'V201G', 'V202', 'V203',
                           'V301','V302','V303','V304','V305','V306',
                           'V401','V402','V403','V404','V405','V406','V407',
                           'V501H','V502H','V503H',
                           'V504H', 'V505H',])

        device.pumps_off(Helpers.all_pumps)

    def pumpVacuumCanWithB2(self, parameters):
        sw = self.stopwatch()
        # close the service manifold valves
        device.valves_off(
            [
                "V101",
                "V102",
                "V104",
                "V105",
                "V106",
                "V107",
                "V108",
                "V109",
                "V110",
                "V111",
                "V112",
                "V113",
                "V114",
                "V303",
                "V306",
                "V404",
                "V406",
            ]
        )
        Helpers.pump_on_turbo(parameters)
        device.pump_on("R2")
        self.wait(45)
        device.valves_on(["V105", "V104"])
        self.wait(30)
        device.valves_on(["V106", "V107"])
        device.valves_off(["V105"])
        self.wait(60)
        device.valves_on(["V101"])
        while (state["P1_PRESSURE"] > parameters["vacuumPressureLimit"]) or (
            state["STILL_TEMPERATURE"] or state["4K_TEMPERATURE"] or state["50K_TEMPERATURE"]
        ) > 70:
            self.wait(5)
            if state["4K_TEMPERATURE"] < state["STILL_TEMPERATURE"]:
                device.heaters_on(["HEATSWITCH_STILL"])
                device.heaters_on(["HEATSWITCH_MXC"])
            if sw.elapsed > 43200:  # 12 hours
                raise ProcedureError(1649, "Cooldown to 4K exceed time limit")
        self.wait(2)

        device.valves_off(['V001', 'V003','V004', 'V005',
                           'V101', 'V102', 'V104', 'V105','V106', 'V107', 'V108', 'V109',
                           'V110', 'V111', 'V112', 'V113','V114',
                           'V201G', 'V202', 'V203',
                           'V301','V302','V303','V304','V305','V306',
                           'V401','V402','V403','V404','V405','V406','V407',
                           'V501H','V502H','V503H',
                           'V504H', 'V505H',])
        device.pumps_off(Helpers.all_pumps)
