from core.api import state
from core.device import device
from core.state_machine.exceptions import ProcedureError, ValidationError
import core.state_machine.procedure as procedure
from typing import TYPE_CHECKING
import math
from datetime import datetime
import core.api
import logging
if TYPE_CHECKING:
    from core.device.command_queue import CommandQueue
import time

logger = logging.getLogger(__name__)

class Helpers:
    service_valves = ['V108', 'V109', 'V110', 'V111']

    # Valves '204NO-206NO' not included as they are quite special
    # TODO Clarify what 'quite special' means (@Frans)
    all_valves = ['V001', 'V003','V004', 'V005',
                  'V101', 'V102', 'V104', 'V105','V106', 'V107', 'V108', 'V109',
                  'V110', 'V111', 'V112', 'V113','V114',
                  'V201G', 'V202', 'V203',
                  'V301','V302','V303','V304','V305','V306',
                  'V401','V402','V403','V404','V405','V406','V407',
                  'V501H','V502H','V503H',
                  'V504H', 'V505H',
                  'V601G', 'V602']

    all_pumps = ['B1A', 'B1B', 'B1C', 'R1A', 'B2', 'R2', 'COM']

    # --- helper methods related to pumping ---

    #Placeholder function for mixture safety in power outage recovery situations
    #TODO write a function that pumps mixture back to tanks
    @staticmethod
   # def mixture_safety(procedure, parameters):
   #     if 'P5_PRESSURE' in procedure.state < parameters['initialTankPressure']:
   #         return ProcReturnError(-1, 'Automation stopped, check mixture amount')
   # ProcReturnError not available...?


    @staticmethod
    def get_circulation_booster_pump_speed():
        if 'B1B_SPEED' in state:
            return state['B1B_SPEED']

        if 'B1C_SPEED' in state:
            return state['B1C_SPEED']

        return state['B1A_SPEED']

    @staticmethod
    def get_turbo_pump_speed(parameters) -> float:
        if parameters.get('serviceBoosterPumpAvailable'):
            return state['B2_SPEED']

        return Helpers.get_circulation_booster_pump_speed()

    @staticmethod
    def pump_off_circulation_booster():
        device.pumps_off(['B1A', 'B1B', 'B1C'])

    @staticmethod
    def pump_on_circulation_booster():
        device.pumps_on(['B1A', 'B1B', 'B1C'])

    @staticmethod
    def pump_on_circulation_pump_R1(parameters):
        device.pumps_on(['R1A'])

    @staticmethod
    def pump_off_circulation_pump_R1(parameters):
        device.pumps_off(['R1A'])

    @staticmethod
    def pump_on_turbo(parameters):
        if parameters['serviceBoosterPumpAvailable']:
            device.pumps_on(['B2'])
        else:
            device.pumps_on(['B1A', 'B1B', 'B1C'])

    @staticmethod
    def pump_off_turbo(parameters):
        if parameters['serviceBoosterPumpAvailable']:
            device.pumps_off(['B2'])
        else:
            device.pumps_off(['B1A', 'B1B', 'B1C'])

    # --- queue helper methods to be used in procedures' enter methods ---

    @staticmethod
    def queue_pump_off_turbo(queue: "CommandQueue", parameters):
        if parameters['serviceBoosterPumpAvailable']:
            queue.queue_pumps_off(['B2'])
        else:
            queue.queue_pumps_off(['B1A', 'B1B', 'B1C'])

    @staticmethod
    def queue_pump_on_turbo(queue: "CommandQueue", parameters):
        if parameters['serviceBoosterPumpAvailable']:
           queue.queue_pumps_on(['B2'])
        else:
            queue.queue_pumps_on(['B1A', 'B1B', 'B1C'])

    @staticmethod
    def queue_pump_rough_final_state(queue: "CommandQueue", parameters):
        queue.queue_valves_off(['V114', 'V113', 'V102', 'V112', 'V105', 'V201G', 'V202'])
        queue.queue_valves_off(Helpers.service_valves)

        queue.queue_valves_on(['V101'])

        if parameters['serviceBoosterPumpAvailable']:
            queue.queue_valves_on(['V104', 'V106', 'V107'])
        else:
            queue.queue_valves_on(['V105', 'V114', 'V112', 'V204NO', 'V205NO', 'V206NO'])

        queue.queue_pumps_on(['R2'])

    @staticmethod
    def queue_close_critical_valves(queue: "CommandQueue", parameters):
        """Makes sure that critical valves and pumps are closed/turned off and adds them to the queue"""

        queue.queue_pumps_off(['R2'])
        queue.queue_valves_off(['V112', 'V113', 'V114', 'V203', 'V004', 'V003', 'V005', 'V403', 'V502H', 'V504H', 'V505H',
                                'V101', 'V104'])

        if parameters['serviceBoosterPumpAvailable']:
            queue.queue_pumps_off(['B2'])
            queue.queue_valves_off(['V106', 'V107'])
        else:
            queue.queue_valves_off(['V105'])

    @staticmethod
    def close_critical_valves(parameters):
        """Makes sure that critical valves and pumps are closed/turned off"""

        #procedure.pumps_off(['R2'])
        device.valves_off(['V112', 'V113', 'V114', 'V203', 'V004', 'V003',
                              'V005', 'V403', 'V502H', 'V504H', 'V505H', 'V101', 'V104'])

        if parameters['serviceBoosterPumpAvailable']:
            #procedure.pumps_off(['B2'])
            device.valves_off(['V106', 'V107'])
        else:
            device.valves_off(['V105'])

    @staticmethod
    def warmup_heater_on(parameters):
        if parameters['numberOf4KHeaters'] == 1:
            device.heater_on('4K_HEATER_1_ENABLED')
        elif parameters['numberOf4KHeaters'] == 2:
            device.heater_on('4K_HEATER_1_ENABLED')
            device.heater_on('4K_HEATER_2_ENABLED')
        elif parameters['numberOf4KHeaters'] == 3:
            device.heater_on('4K_HEATER_1_ENABLED')
            device.heater_on('4K_HEATER_2_ENABLED')
            device.heater_on('4K_HEATER_3_ENABLED')
        elif parameters['numberOf4KHeaters'] == 4:
            device.heater_on('4K_HEATER_1_ENABLED')
            device.heater_on('4K_HEATER_2_ENABLED')
            device.heater_on('4K_HEATER_3_ENABLED')
            device.heater_on('4K_HEATER_4_ENABLED')

    @staticmethod
    def warmup_heater_off(parameters):
        if parameters['numberOf4KHeaters'] == 1:
            device.heater_off('4K_HEATER_1_ENABLED')
        elif parameters['numberOf4KHeaters'] == 2:
            device.heater_off('4K_HEATER_1_ENABLED')
            device.heater_off('4K_HEATER_2_ENABLED')
        elif parameters['numberOf4KHeaters'] == 3:
            device.heater_off('4K_HEATER_1_ENABLED')
            device.heater_off('4K_HEATER_2_ENABLED')
            device.heater_off('4K_HEATER_3_ENABLED')
        elif parameters['numberOf4KHeaters'] == 4:
            device.heater_off('4K_HEATER_1_ENABLED')
            device.heater_off('4K_HEATER_2_ENABLED')
            device.heater_off('4K_HEATER_3_ENABLED')
            device.heater_off('4K_HEATER_4_ENABLED')

    @staticmethod
    def pumps_snapshot():
        initial_pumps_state = {}

        for p in Helpers.all_pumps:
            initial_pumps_state[p+'_ENABLED'] = state[p+'_ENABLED']
        return initial_pumps_state

    @staticmethod
    def restore_initial_pumps_state(initial_pumps_state):

        logger.info("Restore pumps to their initial configuration before the procedure")
        for p in Helpers.all_pumps:
            if initial_pumps_state[p+'_ENABLED']:
                device.pumps_on([p])
            else:
                device.pumps_off([p])

    @staticmethod
    def valves_snapshot():

        initial_valves_state = {}
        for v in Helpers.all_valves:
            initial_valves_state[v+'_ENABLED'] = state[v+'_ENABLED']

        return initial_valves_state

    @staticmethod
    def restore_initial_valves_state(initial_valves_state):

        logger.info("Restore valves to their initial configuration before the procedure")
        for v in Helpers.all_valves:
            if initial_valves_state[v+'_ENABLED']:
                device.valves_on([v])
            else:
                device.valves_off([v])


    @staticmethod
    def get_FSEpos(procedure):
        return procedure.state['FSE_ACTUAL_POSITION']




    @staticmethod
    def get_FSEpos():
        return state['FSE_ACTUAL_POSITION']

    @staticmethod
    def set_FSEpos(pos, max_pos):
        logger.info("Probe moving to the position (m):")
        logger.info(pos)

        device.set_fse_target(float(pos))


        if state["FSE_ENABLED"] == False:
            device.enable_fse()


        device.fse_motor_start()
        time.sleep(0.5)
        sw = procedure.Stopwatch()
        target_position_reached = False

        mock_testing = False # Change to "True", if the testing setup can't rely on the FSE force sensor
        if not mock_testing:
            if pos==max_pos:
                while not state["FSE_FORCE_SENSOR_TRIGGERED"]:
                    time.sleep(1)
                    if (sw.elapsed > 300):
                        raise ProcedureError(1649, "Timeout - FSE force sensor not triggered")
            else:
                while (sw.elapsed < 300) and not target_position_reached and (pos != max_pos): # 5min timeout, skip the loop if the target is the full-in position
                    if abs(state['FSE_ACTUAL_POSITION']-pos) < 1e-3:
                        target_position_reached = True
                time.sleep(3)
        else:
            while (sw.elapsed < 300) and not target_position_reached and (pos != max_pos): # 5min timeout, skip the loop if the target is the full-in position
                if abs(state['FSE_ACTUAL_POSITION']-pos) < 1e-3:
                    target_position_reached = True
            time.sleep(3)


    @staticmethod
    def initialize_FSE():
        if state['FSE_MOUNTED']:
            device.enable_fse()

        else:
            raise NotImplementedError

    @staticmethod
    def warmupFSE():
        device.enable_fse_fan()
        device.enable_fse_heater()
        return

    @staticmethod
    def checkSafeCirculationMode():
        '''
        Check the state of the cryostat to determine if the system is in SafeCirculationMode
        :return: isSafeCirculating (boolean)
        '''

        # Turbo state
        isTurboOff = False
        if (state['B1A_ENABLED'] or state['B1B_ENABLED'] or state['B1C_ENABLED']) == False:
            isTurboOff = True

        # Circulation pump
        isPumpOn = False
        if state['R1A_ENABLED'] == True:
            if (state['V302_ENABLED'] and state['V304_ENABLED']) == True and state['V303_ENABLED'] == False:
                isPumpOn = True
                # Update automation parameters
                # parameters["primaryCirculatingPumpInUse"] = True
                # parameters["secondaryCirculatingPumpInUsee"] = False
        elif (state['R1B_ENABLED'] == True):
            if (state['V301_ENABLED'] and state['V305_ENABLED']) == True and state['V306_ENABLED'] == False:
                isPumpOn = True
                # Update automation parameters
                # parameters["primaryCirculatingPumpInUse"] = False
                # parameters["secondaryCirculatingPumpInUsee"] = True

        # Trap
        isTrap = False
        if (state['V401_ENABLED'] and state['V402_ENABLED']) == True and state['V404_ENABLED'] == False:
            isTrap = True
            # Update automation parameters
            # parameters["primaryLN2TrapInUse"] = True
            # parameters["secondaryLN2TrapInUse"] = False
        elif (state['V405_ENABLED'] and state['V407_ENABLED']) == True and state['V406_ENABLED'] == False:
            isTrap = True
            # Update automation parameters
            # parameters["primaryLN2TrapInUse"] = False
            # parameters["secondaryLN2TrapInUse"] = True


        # Main Valves
        isValve = False
        if (state['V201G_ENABLED'] and state['V001_ENABLED'] and state['V502H_ENABLED']) == True:
            if (state['V112_ENABLED'] and state['V113_ENABLED'] and state['V114_ENABLED'] and state['V203_ENABLED']) == False:
                isValve = True

        # Return path
        isReturnPath = False
        if state['V005_ENABLED'] == True:
            isReturnPath = True

        isSafeCirculating = False
        if isTurboOff and isPumpOn and isTrap and isValve and isReturnPath:
            isSafeCirculating = True

        return isSafeCirculating

    @staticmethod
    def checkNormalCirculationMode():
        '''
        Check the state of the cryostat to determine if the system is in NormalCirculationMode
        :return: isNormalCirculating (boolean)
        '''

        # Turbo state
        isTurboOn = False
        if (state['B1A_ENABLED'] or state['B1B_ENABLED'] or state['B1C_ENABLED']) == True:
            isTurboOn = True

        # Circulation pump
        isPumpOn = False
        if state['R1A_ENABLED'] == True:
            if (state['V302_ENABLED'] and state['V304_ENABLED']) == True and state['V303_ENABLED'] == False:
                isPumpOn = True
                # Update automation parameters
                # parameters["primaryCirculatingPumpInUse"] = True
                # parameters["secondaryCirculatingPumpInUsee"] = False
        elif (state['R1B_ENABLED'] == True):
            if (state['V301_ENABLED'] and state['V305_ENABLED']) == True and state['V306_ENABLED'] == False:
                isPumpOn = True
                # Update automation parameters
                # parameters["primaryCirculatingPumpInUse"] = False
                # parameters["secondaryCirculatingPumpInUsee"] = True

        # Trap
        isTrap = False
        if (state['V401_ENABLED'] and state['V402_ENABLED']) == True and state['V404_ENABLED'] == False:
            isTrap = True
            # Update automation parameters
            # parameters["primaryLN2TrapInUse"] = True
            # parameters["secondaryLN2TrapInUse"] = False
        elif (state['V405_ENABLED'] and state['V407_ENABLED']) == True and state['V406_ENABLED'] == False:
            isTrap = True
            # Update automation parameters
            # parameters["primaryLN2TrapInUse"] = False
            # parameters["secondaryLN2TrapInUse"] = True


        # Main Valves
        isValve = False
        if (state['V201G_ENABLED'] and state['V001_ENABLED'] and state['V502H_ENABLED']) == True:
            if (state['V003_ENABLED'] and state['V004_ENABLED'] and state['V005_ENABLED'] and \
                state['V112_ENABLED'] and state['V113_ENABLED'] and state['V114_ENABLED'] and \
                state['V202_ENABLED'] and state['V203_ENABLED'] and state['V403_ENABLED'] and \
                state['V501H_ENABLED'] and state['V503H_ENABLED']) == False:
                isValve = True

        # Mixture in circulation
        isTankEmpty = False
        if state["P5_PRESSURE"] < 20e-3:
            isTankEmpty = True


        isNormalCirculating = False
        if isTurboOn and isPumpOn and isTrap and isValve and isTankEmpty:
            isNormalCirculating = True

        return isNormalCirculating
