import logging
from datetime import timedelta

from core.state_machine.operation import Operation
from core.api import state
from core.state_machine.procedure import Direction, Procedure, OperationProcedure
from core.state_machine.exceptions import ProcedureError, ValidationError
from core.device import device
from sm.general.helpers import Helpers



logger = logging.getLogger(__name__)


class RemoveFSECold(Procedure):
  name = "Remove FSE insert when cold"
  operation_name = "Remove FSE insert when cold"
  image_url = "images/Collect_mixture.mp4"
  penalty = timedelta(hours = 1.5)
  required_parameters = ["FSEhomeIn",
                         "FSEfullout",
                         "FSEposition5",
                         "FSEDetachedPositionCold",
                         "systemWarmTemperature",
                         "systemVentedPressure",
                         "initialTankPressure",
                         "mixtureCollectingPressureLimit",
                         "collectExtraMixtureTimeLimit",
                         "softVacuumCycles",
                         "p2PressureLimitMixtureInTank",
                         "p4PressureLimitMixtureInTank",
                         "collectMixtureTimeLimit",
                         "fourKelvinHeaterTemperatureLimit",
                         "tankPressureStabilizationTime",
                         "pressureStabilizationSqLimit",
                         "pulseTubeCoolingFinalTemperature",
                         "tankPressureStabilizationMaxTime",
                         "vacuumPressureLimit",
                         "initialTankPressure",
                         "numberOf4KHeaters",
                         "FSEWarmUpTime",
                         "softFSEVacuumCycles",
                         "softVacuumWithN2",
                         "bypassLN2Trap",
                         ]

  direction = Direction.WARMING

  '''
    Sequence: 
    - Start collection of the helium mixture
    - Wait until P3 < "mixtureCollectingPressureLimit" (50mbar)
    - Open V203
    - Remove the probe
    - Warm up the mxc and still stage to speed up the mixture collection 
    - Warm up the probe
    - Vent the probe
    - Wait for the mixture to be at 95% inside the tank
    - Close valves and turn off the circulation pump
    '''

  def validate(self, parameters, state):
    if not state["P1_ENABLED"]:
      yield ValidationError(1649, "P1 sensor is switched off")
    if state["P1_PRESSURE"] > parameters["vacuumPressureLimit"]:
      yield ValidationError(1649, "Vacuum can pressure is too high")
    if state["V601G_ENABLED"] == False:
      yield ValidationError(1649, "FSE insert is already out.")
    if state['4K_TEMPERATURE'] > 70 or state['STILL_TEMPERATURE'] > 70:
      yield ValidationError(1649, "4K flange, still or mixing chamber temperature too high")
    if state["FSE_MOUNTED"] == False:
      yield ValidationError(1649,"The FSE should be connected to the vacuum can")
    if state["HELIUM_TANK_VALUE"] < 75:
      yield ValidationError(1649, "Open the helium tank manual valve")

  def enter(self, parameters):
    self.wait(2)
    device.heater_off("STILL_HEATER")
    Helpers.pump_off_circulation_booster()
    self.command_queue.queue_valves_off(["V402","V403","V407"])
    self.command_queue.queue_valves_on(['V005'])
    device.ln2_trap1_led_off("LED_LN2_TRAP")

    self.command_queue.queue_valves_off(["V101","V102","V104","V105","V106","V107","V108","V109","V110","V111","V112",
                                         "V113","V114","V303","V306","V404","V406","V503H", "V501H"])
    self.command_queue.queue_valves_on(['V502H'])
    self.command_queue.queue_pumps_off(["COM","R2","B2","B1A","B1B","B1C"])

  def procedure(self, parameters):



    logger.info("Entering the mixture collecting phase")



    device.valves_off(["V402","V403","V407"]) # Close trap entrance
    device.ln2_trap1_led_off("LED_LN2_TRAP")
    logger.info("Open return path to tank and turn off Turbo 1")
    Helpers.pump_off_circulation_booster()
    device.valves_on(["V005"])

    Helpers.initialize_FSE()

    FSE_halfway_bool = ((state['FSE_ACTUAL_POSITION']-(parameters['FSEhomeIn']-parameters['FSEDetachedPositionCold']-30e-3)) < 0) # if false, FSE is close to the detached position

    if not FSE_halfway_bool: # go full in only if the FSE was in detached position
      logger.info("FSE insert goes to FSEposition5 and confirm detached mechanism triggered")
      Helpers.set_FSEpos(pos=parameters["FSEposition5"],max_pos=parameters["FSEposition5"])
      self.wait(5)
      Helpers.set_FSEpos(pos=(state['FSE_ACTUAL_POSITION']-parameters['FSEDetachedPositionCold']),max_pos=parameters["FSEposition5"])
      self.wait(5)
      Helpers.set_FSEpos(pos=parameters["FSEposition5"],max_pos=parameters["FSEposition5"])
      self.wait(5)

    logger.info("FSE insert goes to FSEfullout")
    Helpers.set_FSEpos(pos=parameters["FSEfullout"],max_pos=parameters["FSEposition5"])
    self.wait(5)

    if Helpers.get_FSEpos() < 10e-3:
      device.valve_off("V601G")
      self.wait(5)
    else:
      raise ProcedureError(1649, "FSE insert not fully out")

    if state["V601G_ENABLED"] == True:
      raise ProcedureError(1649, "FSE gate valve didn't close properly")


    device.valves_off(["V101","V102","V104","V105","V106",
                       "V107","V108","V109","V110","V111","V112",
                       "V113","V114","V303","V306","V404","V406"])

    self.StartMixtureCollection(parameters)



    # Collect mixture faster
    device.heater_power("STILL_HEATER",heater_channel=3,power= 0.4)
    device.heater_power("MXC_HEATER",heater_channel=4,power= 0.4)
    device.heater_on("STILL_HEATER")
    device.heater_on("MXC_HEATER")


    if state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]:
      logger.info(f"Warm up the FSE insert for a duration of {parameters['FSEWarmUpTime']/60:.0f} min")
      device.enable_fse_fan()
      self.wait(1)
      device.enable_fse_heater()
      logger.info("Softening FSE vacuum n times")

      # Soften FSE vacuum N times
      for i in range(parameters["softFSEVacuumCycles"]):
        if not parameters["softVacuumWithN2"]:
          device.valve_on("V110")
          self.wait(5)
          device.valve_off("V110")
        else:
          device.valve_on("V111")
          self.wait(5)
          device.valve_off("V111")
        self.wait(5)
        if state["P6_PRESSURE"] < 1.05: # safety: open to VC only if no P6 overpressure
          device.valves_on(["V109", "V602"])
          self.wait(5)
          device.valves_off(["V109", "V602"])
          self.wait(2)
        else:
          logger.info("Overpressure of P6, abort softening of FSE vacuum")
          logger.info("Release overpressure with vent port V110")
          device.valve_on("V110")
          self.wait(5)
          device.valve_off("V110")
          self.wait(2)


      sw = self.stopwatch()
      while sw.elapsed < parameters["FSEWarmUpTime"]:
        self.wait(5)
        if state["FSE_LIFT_TEMPERATURE"] > (273.15+55):
          device.disable_fse_heater()
          self.wait(60)
        if state["FSE_LIFT_TEMPERATURE"] < (273.15+50):
          device.enable_fse_heater()
          self.wait(15)
        if state["P4_PRESSURE"]> 0.95*parameters["initialTankPressure"]:
          device.heater_off("STILL_HEATER")
          device.heater_off("MXC_HEATER")

      device.disable_fse_heater()
      self.wait(10)
      device.disable_fse_fan()

      logger.info("Stop warming up the FSE insert")

    if state["P4_PRESSURE"]< 0.95*parameters["initialTankPressure"]:
      device.heater_power("STILL_HEATER",heater_channel=3,power= 0.4)
      device.heater_power("MXC_HEATER",heater_channel=4,power= 0.4)
      device.heater_on("STILL_HEATER")
      device.heater_on("MXC_HEATER")
      while state["P4_PRESSURE"]< 0.95*parameters["initialTankPressure"]:
        self.wait(10)
    device.heater_off("STILL_HEATER")
    device.heater_off("MXC_HEATER")

    logger.info("Waiting for the system to cool to the 4K final temperature...")
    sw = self.stopwatch()
    while (
        state["STILL_TEMPERATURE"] > 6
        or state["4K_TEMPERATURE"] > 4.5
        or state["MXC_TEMPERATURE"] > 6.2
    ):
      if sw.elapsed > 86400: # 2 hours
        raise ProcedureError(1649, "Timeout cooldown to 4K")
      self.wait(60)


    logger.info("Stop pumping")

    list_valves = []  # Valves depending on of the trap and circulation pump in use
    list_valves.append("V401")

    for i in ["V502H", "V504H",  "V203", "V201G", "V001", "V005"]:
      list_valves.append(i)

    for i in ["V302", "V304"]:
      list_valves.append(i)

    for valve in list_valves:
      device.valve_off(valve)
      self.wait(10)

    Helpers.pump_off_circulation_pump_R1(parameters)

  def StartMixtureCollection(self,parameters):
    device.valves_off(["V301","V305","V402","V403","V407"])

    if state["R1A_ENABLED"] == False:
      device.pumps_on(["R1A"])
      self.wait(30)
    device.valves_on(["V001","V005","V302","V304"])
    self.wait(5)
    if state['V201G_ENABLED'] == False:
      device.valves_on(['V202'])
      self.wait(5)
      device.valves_on(['V201G'])
      self.wait(1)
      device.valves_off(['V202'])

    self.wait(5)
    device.valves_on(["V203","V502H"])


    logger.info("Wait for Turbo 1 to wind down (< 100Hz)")
    while state["B1A_SPEED"] > 100:  # Wait for the turbo spin down below 100Hz
      self.wait(10)

    logger.info("Checking that condensing pressure drops")

    sw = self.stopwatch()
    while (
        state["P3_PRESSURE"] > parameters["mixtureCollectingPressureLimit"]
        and sw.elapsed < parameters["collectExtraMixtureTimeLimit"]
    ):
      # not all collected, continue collecting
      self.wait(30)

    # Pump cond-side and trap empty
    device.valve_on("V203")

    device.heater_on("HEATSWITCH_STILL")
    device.heater_on("HEATSWITCH_MXC")
    device.heater_off("STILL_HEATER")

class InsertFSECold(Procedure):
  name="Insert FSE cold"
  operation_name="Insert FSE when cold"
  image_url="images/Condensing.mp4"
  penalty=timedelta(hours=3)
  required_parameters = [
    "vacuumPressureErrorTolerance",
    "pumpTurboFinalPressure",
    "serviceBoosterPumpAvailable",
    "stillHeatingPower",
    "vacuumPressureLimit",
    "initialTankPressure",
    "pumpTurboFSEFinalPressure",
    "FSEposition1",
    "FSEposition2",
    "FSEposition3",
    "FSEposition4",
    "FSEposition5",
    "FSEhomeIn",
    "FSEfullout",
    "FSEpos6duration",
    "serviceBoosterPumpAvailable",
    "condensingTriggerHeatswitches",
    "systemBlockedTimer",
    "condensingPressureDropMaxTime",
    "condensingPressureDifferenceMaxTime",
    "pumpRoughFinalPressure",
    "pumpTurboFSEFinalPressure",
    "roughPumpingMaxTime",
    "turboPumpingMaxTime",
    "FSEDetachedPositionCold",
    "bypassLN2Trap"
  ]

  '''
  sequence:
  - Pump FSE
  - Pump VC
  - Insert the probe in a 5 step sequence
  - stop VC pumping
  - Wait for Tstill < 12K 
  - Close V005
  - Condense the mixture
  '''
  direction = Direction.COOLING

  @classmethod
  def display_name(cls, operation: Operation, parameters, state):
    FSE_in_bool = (abs(state['FSE_ACTUAL_POSITION']-(parameters['FSEhomeIn']-parameters['FSEDetachedPositionCold']))< 20e-3)

    if FSE_in_bool:
      return "Condensing"
    elif not FSE_in_bool:
      return "Insert FSE and condense"
    else:
      return "FSE in - Condensing"


  def validate(self, parameters,state):
    if not state["P1_ENABLED"]:
      yield ValidationError(1649, "P1 sensor is switched off")
    if "FSE" in state:
      if state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 6:
        yield ValidationError(1649, "System is too warm to start cold insertion of the FSE insert")
    else:
      if state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 5.3:
        yield ValidationError(1649, "System is too warm to start cold insertion of the FSE insert")

    if state["P5_PRESSURE"] < 0.9*parameters["initialTankPressure"]:
      yield ValidationError(1649, "Helium mixture should be back in the tank prior to insert of the FSE insert")
    if state["P1_PRESSURE"] > parameters["vacuumPressureLimit"]:
      yield ValidationError(1649, "Vacuum can pressure is too high")
    if state["HEATSWITCH_MXC_ENABLED"] == False or state["HEATSWITCH_STILL_ENABLED"] == False:
      yield ValidationError(1649,
                            "Cryostat should have heatswitches turned ON",
                            )
    if state["FSE_MOUNTED"] == False:
      yield ValidationError(1649,"FSE not connected to the vacuum can")
    if state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
      yield ValidationError(1649, "FSE pressure > pumpTurboFSEFinalPressure")
    if state["HELIUM_TANK_VALUE"] < 75:
      yield ValidationError(1649, "Open the helium tank manual valve")

  def enter(self, parameters):
    device.heaters_off(["STILL_HEATER","MXC_HEATER"])
    if abs(state['FSE_ACTUAL_POSITION']-(parameters['FSEhomeIn']-parameters['FSEDetachedPositionCold']))> 20e-3: # check if the FSE is inserted
      logger.info("Pump FSE")

      device.valves_off(["V601G"])
      self.wait(1)
      device.pumps_on(["R2","B2"])
      self.wait(5)
      device.valves_off(["V001","V003","V004","V005","V102","V105","V108","V110","V111","V112",
                         "V113","V114","V202","V203","V303","V306","V401","V402","V403",
                         "V404","V405","V406","V501H","V502H","V503H"])
      self.wait(1)
      device.valves_on(["V104","V106","V107","V109","V602"])
      self.wait(1)
      while state["B2_SPEED"] < 800: # Hz
        self.wait(1)
      device.disable_fse_heater()
      self.wait(1)
      device.disable_fse_fan()

  def procedure(self, parameters):

    if state["P5_PRESSURE"] < 0.95*parameters["initialTankPressure"]:
      logger.info("Collect remaining mixture")
      if state["R1A_ENABLED"] == False:
        device.pumps_on(["R1A"])
        self.wait(20)
      device.valves_off(["V402","V403","V407"])
      self.wait(1)
      device.valves_on(["V001","V203","V302","V304","V005"])


    if state['V201G_ENABLED'] == False:
      device.valves_on(['V202'])
      self.wait(5)
      device.valves_on(['V201G'])
      self.wait(1)
      device.valves_off(['V202'])

    if abs(state['FSE_ACTUAL_POSITION']-(parameters['FSEhomeIn']-parameters['FSEDetachedPositionCold']))> 20e-3: # check if the FSE is inserted

      # Insert FSE probe
      logger.info("Pump on the vacuum can during the insertion")

      device.pump_on("R2")
      Helpers.pump_on_turbo(parameters)
      self.wait(30)
      device.valves_on(["V104"])

      if state["P6_PRESSURE"] > 1e-3:
        device.valves_on(["V105"])
        while state["P6_PRESSURE"] > 1e-3:
          self.wait(10)
        device.valves_off(["V105"])
      device.valves_on(["V106", "V107"])
      while state["B2_SPEED"] < 900: # in Hz
        self.wait(10)

      while state["P6_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
        self.wait(10)

      device.valves_off(["V109","V602"])
      self.wait(2)
      device.valves_on(["V101"])

      logger.info("Start inserting FSE insert")

      if abs(state['P1_PRESSURE']-state['P8_PRESSURE']) < 30e-3:
        device.valves_on(["V601G"])
        self.wait(3)
        device.valves_on(["V601G"])
      else:
        raise ProcedureError(1649, "Difference of pressure too high to operate the gate valve V601G")
      self.wait(5)

      if state["V601G_ENABLED"] == False:
        raise ProcedureError(1649, "FSE gate valve didn't open properly")

      Helpers.initialize_FSE()

      logger.info("FSE insert goes to FSEfullout")
      logger.info(parameters)
      Helpers.set_FSEpos(pos=parameters["FSEfullout"], max_pos=parameters["FSEposition5"])

      logger.info("FSE insert goes to FSEposition1")
      Helpers.set_FSEpos(pos=parameters["FSEposition1"], max_pos=parameters["FSEposition5"])
      sw = self.stopwatch()
      logger.info("FSE insert thermalization: Wait 20min")
      while sw.elapsed < 1200:  # wait 20min
        self.wait(10)

      logger.info("FSE insert goes to FSEposition2")
      Helpers.set_FSEpos(pos=parameters["FSEposition2"], max_pos=parameters["FSEposition5"])
      logger.info("FSE insert thermalization: Wait 40min")
      sw = self.stopwatch()
      while sw.elapsed < 2400:  # wait 40min
        self.wait(10)

      logger.info("FSE insert goes to FSEposition3")
      Helpers.set_FSEpos(pos=parameters["FSEposition3"], max_pos=parameters["FSEposition5"])
      logger.info("FSE insert thermalization: Wait 15min")
      sw = self.stopwatch()
      while sw.elapsed < 900:  # wait 15min
        self.wait(10)

      logger.info("FSE insert goes to FSEposition4")
      Helpers.set_FSEpos(pos=parameters["FSEposition4"], max_pos=parameters["FSEposition5"])
      logger.info("FSE insert thermalization: Wait 3min")
      sw = self.stopwatch()
      while sw.elapsed < 120:  # wait 3min
        self.wait(10)

      temp = 0
      logger.info("FSE insert goes to FSEposition5")
      while temp < 3:
        Helpers.set_FSEpos(pos=parameters["FSEposition5"], max_pos=parameters["FSEposition5"])
        sw = self.stopwatch()
        while sw.elapsed < 120:  # wait 3min
          self.wait(10)
        temp = temp + 1



      FSEposition6 = Helpers.get_FSEpos() - parameters["FSEDetachedPositionCold"]  # detached position


      logger.info("FSE insert goes to FSEposition6")
      Helpers.set_FSEpos(pos=FSEposition6, max_pos=parameters["FSEposition5"])
      sw = self.stopwatch()
      while sw.elapsed < 60:  # wait 1min
        self.wait(10)
      device.disable_fse()



      logger.info("Stop pumping vacuum can")
      device.valves_off(["V101"])
      self.wait(1)
      device.valves_off(["V104", "V105", "V106", "V107","V109"])
      Helpers.pump_off_turbo(parameters)
      device.pump_off("R2")


      logger.info("Wait for Tstill < 12 K")
      sw = self.stopwatch()
      while state["STILL_TEMPERATURE"] > 12:
        if sw.elapsed > parameters["FSEpos6duration"]:
          raise ProcedureError(1649, "Error: FSE insert takes too long to cooldown")
        self.wait(10)
    else:
      logger.info('Entering CondensingHighPressure')

      device.valves_on(["V204NO", "V205NO", "V206NO"])
      device.pump_off("R2")
      device.valves_off(['V101','V003','V004','V005','V301','V305','V403','V402',
                         'V407','V401','V405','V501H','V503H','V502H'])
      Helpers.pump_off_turbo(parameters)
      if parameters["serviceBoosterPumpAvailable"]:
        device.valves_off(['V104', 'V106', 'V107'])
      else:
        device.valves_off(['V105', 'V114', 'V112'])
      device.pumps_off(['B1A', 'B1B', 'B1C'])

    device.valves_off(["V001","V003","V004","V005",
                       "V101","V112","V113","V114","V202","V203","V301",
                       "V302","V304","V305","V303","V306",
                       "V401","V402","V403","V404","V405","V406","V407",
                       "V501H","V502H","V503H"])



    # High pressure condensing
    logger.info("Initializing condensing")
    self.initialize_condensing(parameters)

    logger.info("Condensing: Condensing High P5: Entering the P5 > 250 and valve V003 condensing loop")

    heat_switch_trigger_pressure = state["P5_PRESSURE"] - parameters["condensingTriggerHeatswitches"]

    sw_high_pressure = self.stopwatch()
    while state["P5_PRESSURE"] > 0.250:
      self.iterate_condensing_high_loop(parameters, heat_switch_trigger_pressure)
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

    # Low pressure condensing
    while state["P5_PRESSURE"] > 0.050:
      self.iterate_condensing_low_loop(parameters)

    device.valve_off("V004")
    device.valve_on("V001")

    # Condensing finalization
    self.condensing_finalization(parameters)


  def initialize_condensing(self, parameters):
    if state["P5_PRESSURE"] < parameters["initialTankPressure"] - 0.2:
      device.heaters_off(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])
    else:
      device.heaters_on(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

    Helpers.pump_off_circulation_booster()

    while Helpers.get_circulation_booster_pump_speed() > 50:
      logger.info("Waiting for circulation booster pump to slow down")
      self.wait(15)

    Helpers.close_critical_valves(parameters)

    logger.info("Condensing: Condensing Init: Initializing circulation")

    if not parameters["bypassLN2Trap"]:
      device.valves_on(["V401", "V402"])
    else:
      device.valves_on(["V403"])
    device.valves_on(["V501H", "V503H", "V302", "V304", "V504H"])
    device.pumps_on(["COM"])

    Helpers.pump_on_circulation_pump_R1(parameters)

    self.wait(10)

    device.valves_on(["V202", "V001"])

    self.wait(60)

    device.valve_on("V201G")
    device.valve_off("V202")

  def iterate_condensing_high_loop(self, parameters, heat_switch_trigger_pressure):
    """
    Auxiliary method containing the logic for the main loop iterated during CondensingHighPressure.
    Using valves V001 and V003, we first have P4_PRESSURE be over 0.9, and after that wait until it goes below 0.6.
    """
    device.valve_on("V003")
    device.valve_off("V001")

    # First we wait for P4_PRESSURE to be over 0.9
    sw = self.stopwatch()
    while state["P4_PRESSURE"] < 0.900:
      self.wait(0.5)

      if sw.elapsed > 180:
        # If P4_PRESSURE did not grow fast enough, raise an error

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
        device.valves_off(["V503H", "V402","V403","V407"])

        logger.info("Condensing: Condensing High P5 — Error: Turning on V202, V203, V502H, V005")
        device.valves_on(["V202", "V203", "V502H", "V005"])

        self.wait(10)

        logger.info("Condensing: Condensing High P5 — Error: Turning off valve V501H")
        device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture

        raise ProcedureError(1649, "System not condensing, check system manual for troubleshooting")

  def iterate_condensing_low_loop(self, parameters):
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
            "Turning off COM (helium compressor) and valves V503H, V402, V403, V407"
        )
        device.pump_off("COM")
        device.valves_off(["V503H", "V402", "V403", "V407"])

        logger.info("Condensing: Condensing High P5 — Error: Turning on V202, V203, V502H, V005")
        device.valves_on(["V202", "V203", "V502H", "V005"])

        self.wait(10)

        logger.info("Condensing: Condensing High P5 — Error: Turning off valve V501H")
        device.valve_off("V501H")  # Could be appended with a procedure to collect all condensed mixture

        raise ProcedureError(1649,
                             "System not condensing, chech the system manual for troubleshooting",
                             )

  def condensing_finalization(self, parameters):
    """
    Auxiliary method containing the logic for the final stage of the mixture condensing
    """

    logger.info("CondensingFinalization: Entering CondensingFinalization")
    logger.info("CondensingFinalization: Tank pressure below 50 mbar, pump remaining gas into circulation")
    device.valve_on("V004")
    self.wait(420)
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
    logger.info("Wait 20min before applying still heat")
    self.wait(1200)  # Give time to apply still heat

    device.heater_on("STILL_HEATER")
    device.heater_power("STILL_HEATING_POWER", 3, parameters["stillHeatingPower"])
    logger.info("Apply default Still heater power")
    logger.info("System cooling to base temperature")

class PumpFSEBellowCold(OperationProcedure):
  name="Pump FSE"
  operation_name="Pump FSE"
  image_url="images/4K.mp4"
  penalty=timedelta(hours=0.5)
  required_parameters = [
    "vacuumPressureErrorTolerance",
    "pumpTurboFinalPressure",
    "serviceBoosterPumpAvailable",
    "vacuumPressureLimit",
    "initialTankPressure",
    "pumpTurboFSEFinalPressure",
    "serviceBoosterPumpAvailable",
    "pumpRoughFinalPressure",
    "pumpTurboFSEFinalPressure",
    "roughPumpingMaxTime",
    "turboPumpingMaxTime",
    "FSEhomeIn",
    "FSEfullout",
    "FSEposition5",
    'FSEDetachedPositionCold',
  ]

  '''
  sequence:
  - Pump FSE
  '''
  direction = Direction.COOLING

  @classmethod
  def display_name(cls, operation: Operation, parameters, state):
    FSE_in_bool = (abs(state['FSE_ACTUAL_POSITION']-(parameters['FSEhomeIn']-parameters['FSEDetachedPositionCold']))< 20e-3)

    if FSE_in_bool:
      return "Confirm FSE loaded"
    elif not FSE_in_bool:
      return "Pump FSE for cold insertion"
    else:
      return "Pump FSE for cold insertion"

  def validate_operation(self, from_procedure, operation, parameters, state):
    if state["PLC_LOCAL_ENABLED"] == True:
      yield ValidationError(1649, "GHS local control is active, please lock the user interface to run operations")

  def validate(self, parameters,state):
    if "FSE" in state:
      if state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 6:
        yield ValidationError(1649, "System is too warm to start cold insertion of the FSE insert")
    else:
      if state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 5.3:
        yield ValidationError(1649, "System is too warm to start cold insertion of the FSE insert")

    if state["P5_PRESSURE"] < 0.9*parameters["initialTankPressure"]:
      yield ValidationError(1649, "Helium mixture should be back in the tank prior to insert the FSE insert")
    if state["P1_PRESSURE"] > parameters["vacuumPressureLimit"]:
      yield ValidationError(1649, "Vacuum can pressure is too high")
    if state["FSE_MOUNTED"] == False:
      yield ValidationError(1649,"The FSE should be connected to the vacuum can")
    if state["HEATSWITCH_MXC_ENABLED"] == False or state["HEATSWITCH_STILL_ENABLED"] == False:
      yield ValidationError(1649,
                            "Cryostat should have heatswitches turned ON",
                            )

  def enter(self, parameters):
    #logger.info("Entering InsertProbeCold.")
    logger.info("Closing service manifold valves")
    if abs(state['FSE_ACTUAL_POSITION']-(parameters['FSEhomeIn']-parameters['FSEDetachedPositionCold']))> 20e-3: # check if the FSE is inserted
      if state['FSE_ACTUAL_POSITION'] > 0:
        logger.info("Move FSE to initial position")
        Helpers.set_FSEpos(pos=parameters["FSEfullout"], max_pos=parameters["FSEposition5"])

      if state["V601G_ENABLED"] == True:
        device.valves_off(["V601G"])
      self.wait(5)

    self.command_queue.queue_valves_off(
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
          "V602",
        ]
    )
    device.disable_fse_heater()
    self.wait(1)
    device.disable_fse_fan()

  def procedure(self, parameters):
    if not state["P1_ENABLED"]:
      device.set_cold_cathode("P1")

    if abs(state['FSE_ACTUAL_POSITION']-(parameters['FSEhomeIn']-parameters['FSEDetachedPositionCold']))> 20e-3: # check if the FSE is inserted
      # Pump FSE with rough pump
      if state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
        logger.info("FSE: Starting PumpRoughFSE")

        self.wait(2)

        device.pump_on("R2")
        self.wait(45)
        device.valves_on(["V104","V105", "V109", "V602"])

        sw = self.stopwatch()
        while sw.elapsed < parameters["roughPumpingMaxTime"]:
          logger.info("PumpRough in progress, until P8 < pumpRoughFinalPressure")

          if (state["P1_PRESSURE"] > state["P8_PRESSURE"]) and state["V101_ENABLED"] == False: # pump VC if P1>P8
            logger.info("Start pumping VC")
            device.valves_on(["V101"])

          if state["P8_PRESSURE"] < parameters["pumpRoughFinalPressure"]:
            break
          else:
            self.wait(10)
        if sw.elapsed > parameters["roughPumpingMaxTime"]:
          raise ProcedureError(1649, "Rough pumping exceeded time limit")
      else:
        device.valves_on(["V104","V109"])
        if state["P6_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
          device.pump_on("R2")
          self.wait(45)
          device.valves_on(["V105"])
          sw = self.stopwatch()
          while sw.elapsed < parameters["roughPumpingMaxTime"]:
            logger.info("PumpRough manifold in progress, until P6 < pumpRoughFinalPressure")

            if (state["P1_PRESSURE"] > state["P6_PRESSURE"]) and state["V101_ENABLED"] == False: # pump VC if P1>P6
              logger.info("Start pumping VC")
              device.valves_on(["V101"])

            if state["P6_PRESSURE"] < parameters["pumpRoughFinalPressure"]:
              break
            else:
              self.wait(10)
          if sw.elapsed > parameters["roughPumpingMaxTime"]:
            raise ProcedureError(1649, "Rough pumping exceeded time limit")

      # Pump FSE with turbo pump
      logger.info("FSE: Starting PumpTurboFSE")
      device.valves_on(["V106","V107","V109"])
      device.valves_off(["V105"])
      if state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:

        Helpers.pump_on_turbo(parameters)
        device.valves_on(["V602"])

        logger.info("Pumping FSE with booster pump until P8 < pumpTurboFSEFinalPressure and a minimum of 20min")
        self.wait(1200) # 20min
        sw = self.stopwatch()
        while state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
          self.wait(10)
          if (state["P1_PRESSURE"] > state["P8_PRESSURE"]) and state["V101_ENABLED"] == False:
            logger.info("Start pumping VC")
            device.valves_on(["V101"])
          if sw.elapsed > parameters["turboPumpingMaxTime"]:
            raise ProcedureError(1649, "FSE pumping exceeded time limit")
      else:
        Helpers.pump_on_turbo(parameters)
        sw = self.stopwatch()
        while (state["P6_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]) or (state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]):
          self.wait(10)
          if (state["P1_PRESSURE"] > state["P6_PRESSURE"]) and state["V101_ENABLED"] == False:
            logger.info("Start pumping VC")
            device.valves_on(["V101"])
          if state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
            logger.info("Pumping FSE")
            device.valves_on(["V602"])
          if sw.elapsed > parameters["turboPumpingMaxTime"]:
            raise ProcedureError(1649, "Pumping exceeded time limit")
        device.valves_on(["V602"])
        logger.info("Pump FSE for 10min")
        self.wait(600) # 10min

class InsertFSEWarm(Procedure):
  name="Insert FSE warm"
  operation_name="Insert FSE when warm"
  image_url="images/System_Warm.mp4"  # TODO: update the url for probe insertion
  penalty=timedelta(minutes=15)
  required_parameters = [
    "vacuumPressureErrorTolerance",
    "pumpTurboFinalPressure",
    "serviceBoosterPumpAvailable",
    "initialTankPressure",
    "pumpTurboFSEFinalPressure",
    "FSEposition5",
    "systemWarmTemperature",
    "dilutionRefrigeratorEvacuatedPressure",
    "roughPumpingMaxTime",
    "pumpRoughFinalPressure",
    "turboPumpMaxSpeedStartup",
    "vacuumPressureLimit",
    "FSEfullout",
    "turboPumpingMaxTime",
    "FSEDetachedPositionWarm"
  ]

  '''
  sequence:
  ## Rough pump
  - Close manifold valves
  - Pump FSE with rough pump R2
  - Pump VC if P1 > P8
  - Pump until P8 < pumpRoughFinalPressure
  - Skip the whole procedure if P8 < pumpTurboFSEFinalPressure
  
  ## Turbo pump
  - Pump with Turbo 2
  - Pump until P8 < pumpTurboFSEFinalPressure
  - Pump VC if P1 > P8
  - Skip pumping FSE if P8 < pumpTurboFSEFinalPressure
  
  ## Insert Probe
  - Close service manifold valves
  - Turn off rough pump R2 and turbo B2
  - Open gate valve V601G
  - Insert probe to the maximum
  - Go to detached position
  - Disable FSE motor
  '''

  direction = Direction.NEITHER

  def validate(self, parameters,state):
    if (
        state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]
        or state["4K_TEMPERATURE"] < parameters["systemWarmTemperature"]
    ):
      yield ValidationError(1649, "System too cold for warm insertion")
    if state["FSE_ACTUAL_POSITION"] > (parameters["FSEfullout"]+5e-3):
      yield ValidationError(1649, "Probe should be initially at FSEfullout position")
    if state["FSE_MOUNTED"] == False:
      yield ValidationError(1649,"The FSE should be connected to the vacuum can")

  def enter(self, parameters):
    logger.info("Entering InsertFSEProbeWarm. Close service manifold valves.")



    device.valves_off(['V101','V102','V105','V106','V107','V108',
                       'V109','V110','V111','V112','V113','V114',
                       'V303','V306','V404','V406'])

    device.disable_fse_heater()
    self.wait(1)
    device.disable_fse_fan()

  def procedure(self, parameters):

    if state["V601G_ENABLED"] == True:
      device.valves_off(["V601G"])

    ## PumpRoughFSE ###

    if state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
      logger.info("FSE: Starting PumpRoughFSE")

      self.wait(2)

      device.pump_on("R2")
      self.wait(45)
      device.valves_on(["V104","V105", "V109", "V602"])

      sw = self.stopwatch()
      logger.info("PumpRough in progress, until P8 < pumpRoughFinalPressure")
      while sw.elapsed < parameters["roughPumpingMaxTime"]:


        if (state["P1_PRESSURE"] > state["P8_PRESSURE"]) and state["V101_ENABLED"] == False: # pump VC if P1>P8
          logger.info("Start pumping VC")
          device.valves_on(["V101"])

        if state["P8_PRESSURE"] < parameters["pumpRoughFinalPressure"]:
          break
        else:
          self.wait(10)
        if sw.elapsed > parameters["roughPumpingMaxTime"]:
          raise ProcedureError(1649, "Rough pumping exceeded time limit")
    else:
      device.valves_on(["V104","V109"])
      if state["P6_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
        device.pump_on("R2")
        self.wait(45)
        device.valves_on(["V105"])
        sw = self.stopwatch()
        logger.info("PumpRough manifold in progress, until P6 < pumpRoughFinalPressure")
        while sw.elapsed < parameters["roughPumpingMaxTime"]:

          if (state["P1_PRESSURE"] > state["P6_PRESSURE"]) and state["V101_ENABLED"] == False: # pump VC if P1>P6
            logger.info("Start pumping VC")
            device.valves_on(["V101"])

          if state["P6_PRESSURE"] < parameters["pumpRoughFinalPressure"]:
            break
          else:
            self.wait(10)
          if sw.elapsed > parameters["roughPumpingMaxTime"]:
            raise ProcedureError(1649, "Rough pumping exceeded time limit")

    ## PumpTurboFSE ###

    Helpers.pump_on_turbo(parameters)

    if state["R2_ENABLED"] == False:
      device.pump_on("R2")
      self.wait(45)

    if parameters["serviceBoosterPumpAvailable"]:
      device.valves_on(["V107", "V106"])
      device.valves_off(["V105"])
    else:
      raise ProcedureError(1649, "Service booster pump is required to operate the FSE")

    logger.info("FSE: Starting turbo pump the FSE")
    if state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:

      Helpers.pump_on_turbo(parameters)
      device.valves_on(["V602"])

      logger.info("Pumping FSE with booster pump until P8 < pumpTurboFSEFinalPressure")
      sw = self.stopwatch()
      while state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
        self.wait(10)
        if (state["P1_PRESSURE"] > state["P8_PRESSURE"]) and state["V101_ENABLED"] == False:
          logger.info("Start pumping VC")
          device.valves_on(["V101"])
        if sw.elapsed > parameters["turboPumpingMaxTime"]:
          raise ProcedureError(1649, "FSE pumping exceeded time limit")
    else:
      Helpers.pump_on_turbo(parameters)
      device.valves_on(["V104","V106", "V107", "V109", "V602"])
      sw = self.stopwatch()
      while (state["P6_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]) or (state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]):
        self.wait(10)
        if (state["P1_PRESSURE"] > state["P6_PRESSURE"]) and state["V101_ENABLED"] == False:
          logger.info("Start pumping VC")
          device.valves_on(["V101"])
        if state["P8_PRESSURE"] > parameters["pumpTurboFSEFinalPressure"]:
          logger.info("Pumping FSE")
          device.valves_on(["V602"])
        if sw.elapsed > parameters["turboPumpingMaxTime"]:
          raise ProcedureError(1649, "Pumping exceeded time limit")
    device.valves_on(["V602"])
    logger.info("Continue pumping FSE for 10min")
    self.wait(600) # 10min
    logger.info("FSE evacuated")
    Helpers.pump_off_turbo(parameters)
    device.pump_off("R2")

    device.valves_off(["V101", "V102", "V104", "V105","V106",
                       "V107","V108","V109","V110","V111","V112","V113",
                       "V114","V303","V306","V404","V406"])

    ## InsertFSEProbeWarm ##

    device.valves_off(["V602","V109"])
    logger.info("Open gate valve and insert probe")
    self.wait(5)
    device.valves_on(["V601G"])
    self.wait(10)
    if state["V601G_ENABLED"] == False:
      raise ProcedureError(1649, "Error: the gate valve didn't open properly")

    Helpers.initialize_FSE()

    temp = 0
    logger.info("Insert the FSE probe")
    while temp < 3:
      Helpers.set_FSEpos(pos=parameters["FSEposition5"], max_pos=parameters["FSEposition5"])
      sw = self.stopwatch()
      while sw.elapsed < 5:
        self.wait(10)
      temp = temp + 1

    logger.info("FSE moving to warm detached position")
    pos_fullin_warm = Helpers.get_FSEpos()
    Helpers.set_FSEpos(pos=(pos_fullin_warm - parameters["FSEDetachedPositionWarm"]),max_pos=parameters["FSEposition5"])

    device.disable_fse() # Turn off the motor
    logger.info("Exit procedure InsertFSEWarm")

class RemoveFSEWarm(Procedure):
  name="Remove FSE insert warm"
  operation_name="Remove FSE insert warm"
  image_url="images/System_Warm.mp4"  # TODO: update the url for remove probe
  penalty=timedelta(minutes=10)
  required_parameters = [
    "FSEposition5",
    "FSEfullout",
    "FSEpos6duration",
    "systemWarmTemperature",
    "systemVentedPressure",
    "FSEWarmUpTime"
  ]

  '''
  sequence: 
  - Move probe full in
  - Move probe full out
  - close gate valve V601G
  - if Tstill < systemWarm Temperature: turn on FSE heater and fan
  '''

  direction = Direction.NEITHER

  def validate(self, parameters,state):
    if state["V601G_ENABLED"] == False:
      yield ValidationError(1649, "FSE insert is already out.")
    if state["FSE_MOUNTED"] == False:
      yield ValidationError(1649,"The FSE should be connected to the vacuum can")

  def enter(self, parameters):
    logger.info("Entering RemoveProbeFSE.")

    device.valves_off(["V101"])
    self.wait(2)
    device.valves_off(["V102","V104","V105","V106","V107","V108","V109",
                       "V110","V111","V112","V113","V114","V303",
                       "V306","V404","V406","V602"])

    device.disable_fse_heater()
    self.wait(1)
    device.disable_fse_fan()


  def procedure(self, parameters):


    logger.info("Remove the probe")
    Helpers.initialize_FSE()

    Helpers.set_FSEpos(parameters["FSEposition5"],parameters["FSEposition5"])
    self.wait(20)

    logger.info("Moving FSE to full out position")
    Helpers.set_FSEpos(parameters["FSEfullout"],parameters["FSEposition5"])
    self.wait(20)

    if Helpers.get_FSEpos() < 10e-3:
      device.valves_off(["V601G"])
      self.wait(5)
    else:
      raise ProcedureError(1649, "Probe not fully out")

    if state["V601G_ENABLED"] == True:
      raise ProcedureError(1649, "Probe gate valve didn't close properly")

    if state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]:
      logger.info(f"Warm up the FSE insert for a duration of {parameters['FSEWarmUpTime']/60:.0f} min")
      device.enable_fse_fan()
      self.wait(1)
      device.enable_fse_heater()

      sw = self.stopwatch()
      while sw.elapsed < parameters["FSEWarmUpTime"]:
        self.wait(10)
      device.disable_fse_heater()
      self.wait(10)
      device.disable_fse_fan()

    logger.info("Vent the FSE")
    device.valves_off(["V101"])
    self.wait(1)
    device.valves_off(["V102","V104","V105",
                       "V106","V107","V108",
                       "V110","V111","V112",
                       "V113","V114","V303",
                       "V306","V404","V406",
                       "V601G"])
    self.wait(3)
    device.valves_on(["V602","V109","V110"])

    while (
        state["P6_PRESSURE"] < parameters["systemVentedPressure"]
        or state["P8_PRESSURE"] < parameters["systemVentedPressure"]
    ):
      self.wait(2)
    self.wait(4)
    device.valves_off(["V602","V109","V110"])

    logger.info("Exit procedure RemoveFSEWarm")
    #Helpers.restore_initial_valves_state(initial_valves_state)

class PulseTubeCoolingFallbackFSE(Procedure):
  name = "Pulse tube cooling fallback FSE"
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
    "FSEhomeIn",
    "FSEfullout",
    "FSEposition5",
    'FSEDetachedPositionCold',
    "bypassLN2Trap",
  ]

  '''
  Sequence: 
  - Turn on the PTs and Turn off the heatswitches
  - Pump VC if P1 > "vacuumPressureLimit"
  - Turn on heatswitch if Tmxc or Tstill > T4K
  - Wait for T4K < 4.6 K and Tstill < 6 K 
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

    if not state["P1_ENABLED"]:
      device.set_cold_cathode("P1")

    device.pulse_tube_on("PULSE_TUBE")
    device.heaters_off(["HEATSWITCH_MXC", "HEATSWITCH_STILL"])

    if state["P1_PRESSURE"] > parameters["vacuumPressureLimit"]:
      if parameters["serviceBoosterPumpAvailable"]:
        logger.info("P1 pressure too high. Pump VC with B2")
        self.pumpVacuumCanWithB2(parameters)
      else:
        raise ProcedureError(1649, "Service booster pump not available")


    sw = self.stopwatch()
    logger.info("Waiting for the system to cool to the final temperature...")
    while state["4K_TEMPERATURE"] > 4.6 or state["STILL_TEMPERATURE"] > 6:
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


    ## CondensingLowPressure
    device.heater_off("HEATSWITCH_STILL")
    device.heater_off("HEATSWITCH_MXC")
    if state["P5_PRESSURE"] > 0.015:
      while state["P5_PRESSURE"] > 0.050:
        self.iterate_condensing_low_pressure_loop(parameters)

      device.valve_off("V004")
      device.valve_on("V001")
      pass

    ## CondensingFinalization
    logger.info("CondensingFinalization: Entering CondensingFinalization")
    self.condensing_finalization(parameters)

    logger.info("Leaving: PulseTubeCoolingFallbackFSE")

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
      device.ln2_trap1_led_on("LED_LN2_TRAP")
    else:
      device.valves_on(["V403"])


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
            "Turning off COM (helium compressor) and valves V503H, V402, V403, V407"
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


class PumpVCandFSE(Procedure):
  name = "Pump vacuum can and FSE"
  image_url = "images/Vacuum_Pump.mp4"
  penalty = timedelta(minutes=90)
  required_parameters = [
    "dilutionRefrigeratorEvacuatedPressure",
    "roughPumpingMaxTime",
    "turboPumpingMaxTime",
    "pumpRoughFinalPressure",
    "pumpTurboFinalPressure",
    "serviceBoosterPumpAvailable",
    "turboPumpMaxSpeedStartup",
    "vacuumPressureLimit",
    "initialTankPressure",
    "vacuumPressureErrorTolerance",
  ]
  direction = Direction.COOLING

  '''
  Sequence:
  - Turn on P1 sensor
  - Turn on service pump R2, and open path to VC and FSE
  - wait until P1 and P8 < "pumpRoughFinalPressure"
  - Open a pumping path to B2
  - Wait until P1 and P8 < pumpTurboFinalPressure
  '''


  def validate(self, parameters, state):
    if state["P1_PRESSURE"] < parameters["vacuumPressureLimit"]:
      yield ValidationError(1649, "P1 pressure low, no need to pump VC")
    if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
      yield ValidationError(1649, "P5 pressure below limit, check mixture amount")
    if state["P3_PRESSURE"] > parameters["dilutionRefrigeratorEvacuatedPressure"]:
      yield ValidationError(1649, "P3 too large to start cooldown. Evacuate the DR unit volume")
    if state["FSE_MOUNTED"] == False:
      yield ValidationError(1649,"The FSE should be connected to the vacuum can")
    if state["V601G_ENABLED"] == True:
      yield ValidationError(1649, "FSE insert should be out and gate valve V601G closed.")

  def enter(self, parameters):
    logger.info("Entering PumpRough. Closing all valves.")

    self.command_queue.queue_valves_off(Helpers.all_valves)
    self.command_queue.queue_pumps_off(Helpers.all_pumps)
    self.command_queue.queue_valves_on(["V204NO", "V205NO", "V206NO"])

  def procedure(self, parameters):

    if not state["P1_ENABLED"]:
      device.set_cold_cathode("P1")

    if state["R2_ENABLED"] == False:
      device.pump_on("R2")
      self.wait(30)

    if ((state["P1_PRESSURE"] > parameters["pumpRoughFinalPressure"]) or
        (state["P8_PRESSURE"] > parameters["pumpRoughFinalPressure"])):

      # Pump VC and FSE with rough pump
      logger.info("PumpVacuum: Starting PumpRough")

      if state["P8_PRESSURE"] > (state["P1_PRESSURE"] + 30e-3):
        logger.info("Equalize pressures before connecting VC and FSE volume")
        device.valves_on(["V104", "V105", "V109", "V602"])
        while(state["P8_PRESSURE"] > (state["P1_PRESSURE"] + 30e-3)):
          self.wait(1)
        device.valves_on(["V101"])

      elif state["P1_PRESSURE"] > (state["P8_PRESSURE"] + 30e-3):
        logger.info("Equalize pressures before connecting VC and FSE volume")
        device.valves_on(["V101","V104", "V105"])
        self.wait(2)
        while (state["P6_PRESSURE"] > (state["P8_PRESSURE"] + 30e-3)):
          self.wait(1)
        device.valves_on(["V109","V602"])
      else:
        device.valves_on(["V104", "V105", "V101","V109","V602"])

      sw = self.stopwatch()

      logger.info("PumpRough in progress, until P1 < pumpRoughFinalPressure")
      while (
          (state["P1_PRESSURE"] > parameters["pumpRoughFinalPressure"]) or
          (state["P6_PRESSURE"] > parameters["pumpRoughFinalPressure"]) or
          (state["P8_PRESSURE"] > parameters["pumpRoughFinalPressure"])
      ):

        self.wait(10)

        if sw.elapsed > parameters["roughPumpingMaxTime"]:
          raise ProcedureError(1649, "Rough pumping exceeded time limit")

    # Pump VC and FSE with turbo pump
    logger.info("PumpVacuum: Starting PumpTurbo")


    device.valves_on(["V101","V104","V109","V602"])
    Helpers.pump_on_turbo(parameters)

    if parameters["serviceBoosterPumpAvailable"]:
      device.valves_on(["V106", "V107"])
      device.valves_off(["V105"])
    else:
      raise ProcedureError(1649, "Service booster pump needed to operate the FSE")



    logger.info("Pumping VC with booster pump until P1 and P8 < pumpTurboFinalPressure and at least 10min elapsed")
    sw = self.stopwatch()

    while (
        (state["P1_PRESSURE"] > parameters["pumpTurboFinalPressure"]) or
        (state["P8_PRESSURE"] > parameters["pumpTurboFinalPressure"]) or
        (sw.elapsed < 600)
        ):

        self.wait(10)
        if (sw.elapsed > parameters["turboPumpingMaxTime"]):
          raise ProcedureError(1649, "Vacuum can pumping exceeded time limit")


class PumpVCInsertFSEWarm(Procedure):
  name="Pump to vacuum and insert FSE warm"
  operation_name="Pump to vacuum and insert FSE warm"
  image_url="images/Vacuum_Pump.mp4"  # TODO: update the url for probe insertion
  penalty=timedelta(minutes=90)
  required_parameters = [
    "vacuumPressureErrorTolerance",
    "pumpRoughFinalPressure",
    "pumpTurboFinalPressure",
    "pumpTurboFSEFinalPressure",
    "serviceBoosterPumpAvailable",
    "initialTankPressure",
    "FSEposition5",
    "systemWarmTemperature",
    "dilutionRefrigeratorEvacuatedPressure",
    "roughPumpingMaxTime",
    "turboPumpMaxSpeedStartup",
    "vacuumPressureLimit",
    "FSEfullout",
    "turboPumpingMaxTime",
    "FSEDetachedPositionWarm",
  ]

  '''
  sequence:
  
  ## Rough pump VC and FSE
  - Close manifold valves
  - Pump FSE and VC with rough pump R2
  - Pump until P1 and P8 < pumpRoughFinalPressure
  - Skip the whole pumping section if P8 and P1 < pumpTurboFinalPressure
  
  ## Turbo pump VC and FSE
  - Pump with Turbo 2
  - Pump until P1 and P8 < pumpTurboFinalPressure
  - Skip pumping FSE and VC if P1 and P8 < pumpTurboFinalPressure
  
  ## Insert FSE
  - Close service manifold valves
  - Turn off rough pump R2 and turbo B2
  - Open gate valve V601G
  - Insert probe to the maximum
  - Go to detached position
  - Disable FSE motor
  '''

  direction = Direction.COOLING

  def validate(self, parameters,state):
    if (
        state["STILL_TEMPERATURE"] < parameters["systemWarmTemperature"]
        or state["4K_TEMPERATURE"] < parameters["systemWarmTemperature"]
    ):
      yield ValidationError(1649, "System too cold for warm insertion")
    if state["P5_PRESSURE"] < parameters["initialTankPressure"]:
      yield ValidationError(1649, "P5 pressure below limit, check mixture amount")
    if state["P3_PRESSURE"] > parameters["dilutionRefrigeratorEvacuatedPressure"]:
      yield ValidationError(1649, "P3 too large to start cooldown. Evacuate the DR unit volume")
    if state["FSE_MOUNTED"] == False:
      yield ValidationError(1649,"The FSE should be connected to the vacuum can")
    if state["FSE_ACTUAL_POSITION"] > (parameters["FSEfullout"]+5e-3):
      yield ValidationError(1649, "Probe should be initially at FSEfullout position")

  def enter(self, parameters):
    logger.info("Entering PumpVCInsertFSEWarm. Close service manifold valves.")

    self.command_queue.queue_valves_off(Helpers.all_valves)
    self.command_queue.queue_pumps_off(Helpers.all_pumps)
    self.command_queue.queue_valves_on(["V204NO", "V205NO", "V206NO"])

    device.disable_fse_heater()
    self.wait(1)
    device.disable_fse_fan()

  def procedure(self, parameters):

    if state["V601G_ENABLED"] == True:
      device.valves_off(["V601G"])

    if not state["P1_ENABLED"]:
      device.set_cold_cathode("P1")

    if state["R2_ENABLED"] == False:
      device.pump_on("R2")
      self.wait(30)

    if ((state["P1_PRESSURE"] > parameters["pumpRoughFinalPressure"]) or
      (state["P8_PRESSURE"] > parameters["pumpRoughFinalPressure"])):

      # Pump VC and FSE with rough pump
      logger.info("PumpVacuum: Starting PumpRough")

      if state["P8_PRESSURE"] > (state["P1_PRESSURE"] + 30e-3):
        logger.info("Equalize pressures before connecting VC and FSE volume")
        device.valves_on(["V104", "V105", "V109", "V602"])

        while (state["P8_PRESSURE"] > (state["P1_PRESSURE"] + 30e-3)):
          self.wait(1)
        device.valves_on(["V101"])

      elif state["P1_PRESSURE"] > (state["P8_PRESSURE"] + 30e-3):
        logger.info("Equalize pressures before connecting VC and FSE volume")
        device.valves_on(["V101","V104", "V105"])
        self.wait(2)
        while (state["P6_PRESSURE"] > (state["P8_PRESSURE"] + 30e-3)):
          self.wait(1)
        device.valves_on(["V109","V602"])
      else:
        device.valves_on(["V104", "V105", "V101","V109","V602"])

      sw = self.stopwatch()

      logger.info("PumpRough in progress, until P1 < pumpRoughFinalPressure")
      while (
          (state["P1_PRESSURE"] > parameters["pumpRoughFinalPressure"]) or
          (state["P6_PRESSURE"] > parameters["pumpRoughFinalPressure"]) or
          (state["P8_PRESSURE"] > parameters["pumpRoughFinalPressure"])
      ):

        self.wait(10)

        if sw.elapsed > parameters["roughPumpingMaxTime"]:
          raise ProcedureError(1649, "Rough pumping exceeded time limit")


    # Pump VC and FSE with turbo pump
    logger.info("PumpVacuum: Starting PumpTurbo")

    if parameters["serviceBoosterPumpAvailable"]:
      device.valves_on(["V106", "V107"])
      device.valves_off(["V105"])
    else:
      raise ProcedureError(1649, "Service booster pump needed to operate the FSE")

    device.valves_on(["V104", "V101", "V109", "V602"])
    Helpers.pump_on_turbo(parameters)

    logger.info("Pumping VC with booster pump until P1 and P8 < pumpTurboFinalPressure and at least 10min elapsed")
    sw = self.stopwatch()

    while (
        (state["P1_PRESSURE"] > parameters["pumpTurboFinalPressure"]) or
        (state["P8_PRESSURE"] > parameters["pumpTurboFinalPressure"]) or
        (sw.elapsed < 600)
    ):

      self.wait(10)
      if (sw.elapsed > parameters["turboPumpingMaxTime"]):
        raise ProcedureError(1649, "Vacuum can pumping exceeded time limit")
    logger.info("VC and FSE evacuated")




    ## InsertFSEProbeWarm ##

    device.valves_off(["V602","V109"])
    logger.info("Open gate valve and insert probe")
    self.wait(5)
    device.valves_on(["V601G"])
    self.wait(10)
    if state["V601G_ENABLED"] == False:
      raise ProcedureError(1649, "Error: the gate valve didn't open properly")

    Helpers.initialize_FSE()

    temp = 0
    logger.info("Insert the FSE probe")
    while temp < 3:
      Helpers.set_FSEpos(pos=parameters["FSEposition5"], max_pos=parameters["FSEposition5"])
      sw = self.stopwatch()
      while sw.elapsed < 5:
        self.wait(10)
      temp = temp + 1

    logger.info("FSE moving to warm detached position")
    pos_fullin_warm = Helpers.get_FSEpos()
    Helpers.set_FSEpos(pos=(pos_fullin_warm - parameters["FSEDetachedPositionWarm"]),max_pos=parameters["FSEposition5"])

    device.disable_fse() # Turn off the motor

    if state["P1_PRESSURE"] > parameters["pumpTurboFinalPressure"]:
      logger.info("Pump VC until P1 < pumpTurboFinalPressure")
      if state["R2_ENABLED"] == False:
        device.pump_on("R2")
        self.wait(45)
      if state["B2_ENABLED"] == False:
        Helpers.pump_on_turbo(parameters)
        self.wait(45)
      device.valves_on(["V101","V104","V106","V107"])
      sw = self.stopwatch()
      while state["P1_PRESSURE"] > parameters["pumpTurboFinalPressure"]:
        self.wait(5)
        if sw.elapsed > parameters["turboPumpingMaxTime"]:
          raise ProcedureError(1649, "Pumping exceeded time limit")


    logger.info("Exit procedure PumpVCInsertFSEWarm")





  def evacuateDRUnit(self, parameters):

    device.valves_off(["V001", "V003", "V004", "V005",
                       "V101", "V102", "V104", "V106", "V107",
                       "V108", "V109","V110","V111","V112", "V114",
                       "V201G", "V202",
                       "V301","V302","V303","V304","V305","V306",
                       "V401", "V402", "V403", "V404", "V405",
                       "V406","V407",
                       "V501H", "V503H"])

    # Pump DR with rough pump
    logger.info("EvacuateDR: DR volume empty")

    self.wait(2)

    device.pump_on("R2")

    device.valves_on(["V105"])

    logger.info("Pumping service volume until P6_PRESSURE < 1 mbar")

    sw = self.stopwatch()
    while sw.elapsed < parameters["roughPumpingMaxTime"]:

      if state["P6_PRESSURE"] < 0.001:
        return
      else:
        self.wait(2)


    self.wait(4)

    device.valves_on(["V113","V203","V502H"])

    logger.info("Pumping DR unit volume until P3_PRESSURE < dilutionRefrigeratorEvacuatedPressure and 10min elapsed")
    sw = self.stopwatch()
    while sw.elapsed < parameters["roughPumpingMaxTime"]:

      if (state["P3_PRESSURE"] < parameters["dilutionRefrigeratorEvacuatedPressure"]) and (sw.elapsed > 600):
        return
      else:
        self.wait(2)
        if sw.elapsed > 1800:
          yield ValidationError(1649, "Timeout while pumping to DR volume. P3 pressure too high for cooldown")

    device.valves_off(["V105","V113", "V203", "V502H"])



