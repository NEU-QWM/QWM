"""
Direct API calls to devices.

Functions here create the DeviceCommands and call API immediately.
"""

import core.api
from core.device.command import DeviceCommand


def pump_on(device_id):
    core.api.device_command(DeviceCommand.pump_on(device_id))


def pump_off(device_id):
    core.api.device_command(DeviceCommand.pump_off(device_id))


def valve_on(device_id):
    core.api.device_command(DeviceCommand.valve_on(device_id))


def valve_off(device_id):
    core.api.device_command(DeviceCommand.valve_off(device_id))


def heater_on(device_id):
    core.api.device_command(DeviceCommand.heater_on(device_id))


def heater_off(device_id):
    core.api.device_command(DeviceCommand.heater_off(device_id))


def heater_power(heater_device, heater_channel, power):
    core.api.device_command(DeviceCommand.heater_power(heater_device, heater_channel, power))


def pulse_tube_on(device_id):
    core.api.device_command(DeviceCommand.pulse_tube_on(device_id))


def pulse_tube_off(device_id):
    core.api.device_command(DeviceCommand.pulse_tube_off(device_id))


def circulation_turbo_pumps_on(device_id):
    core.api.device_command(DeviceCommand.circulation_turbo_pumps_on(device_id))


def circulation_turbo_pumps_off(device_id):
    core.api.device_command(DeviceCommand.circulation_turbo_pumps_off(device_id))


def valves_on(valves: list[str]):
    for valve in valves:
        valve_on(valve)


def valves_off(valves: list[str]):
    for valve in valves:
        valve_off(valve)


def pumps_on(pumps: list[str]):
    for pump in pumps:
        pump_on(pump)


def pumps_off(pumps: list[str]):
    for pump in pumps:
        pump_off(pump)


def heaters_on(heaters: list):
    for h in heaters:
        heater_on(h)


def heaters_off(heaters: list):
    for h in heaters:
        heater_off(h)


def set_cold_cathode(device_id):
    core.api.device_command(DeviceCommand.set_cold_cathode(device_id))


def ln2_trap1_led_on(device_id):
    core.api.device_command(DeviceCommand.ln2_trap1_led_on(device_id))


def ln2_trap1_led_off(device_id):
    core.api.device_command(DeviceCommand.ln2_trap1_led_off(device_id))


def ln2_trap2_led_on(device_id):
    core.api.device_command(DeviceCommand.ln2_trap2_led_on(device_id))


def ln2_trap2_led_off(device_id):
    core.api.device_command(DeviceCommand.ln2_trap2_led_off(device_id))

def enable_fse():
    core.api.device_command(DeviceCommand.enable_fse())


def disable_fse():
    core.api.device_command(DeviceCommand.disable_fse())


def enable_fse_fan():
    core.api.device_command(DeviceCommand.enable_fse_fan())


def disable_fse_fan():
    core.api.device_command(DeviceCommand.disable_fse_fan())


def enable_fse_heater():
    core.api.device_command(DeviceCommand.enable_fse_heater())


def disable_fse_heater():
    core.api.device_command(DeviceCommand.disable_fse_heater())


def set_fse_target(target_position):
    core.api.device_command(DeviceCommand.fse_target(target_position))


def fse_motor_start():
    core.api.device_command(DeviceCommand.fse_motor_start())


def fse_motor_stop():
    core.api.device_command(DeviceCommand.fse_motor_stop(True))
    # We need to call bMotorStopSW with argument False so the stop command
    # works again
    core.api.device_command(DeviceCommand.fse_motor_stop(False))


def ln2_trap1_led_on(device_id):
    core.api.device_command(DeviceCommand.ln2_trap1_led_on(device_id))


def ln2_trap1_led_off(device_id):
    core.api.device_command(DeviceCommand.ln2_trap1_led_off(device_id))


def ln2_trap2_led_on(device_id):
    core.api.device_command(DeviceCommand.ln2_trap2_led_on(device_id))


def ln2_trap2_led_off(device_id):
    core.api.device_command(DeviceCommand.ln2_trap2_led_off(device_id))

def AMI430_set_target_field(device_id,target_field):
    core.api.device_command(DeviceCommand.AMI430_set_target_field(device_id,target_field))

def AMI430_set_target_current(device_id,target_current):
    core.api.device_command((DeviceCommand.AMI430_set_target_current(device_id,target_current)))

def AMI430_set_coil_constant(device_id,coil_constant):
    core.api.device_command(DeviceCommand.AMI430_set_coil_constant(device_id,coil_constant))

def AMI430_ramp_to_zero(device_id):
    core.api.device_command(DeviceCommand.AMI430_ramp_to_zero(device_id))

def AMI430_ramp_to_zeros(instruments: list[str]):
    for instrument in instruments:
        AMI430_ramp_to_zero(instrument)

def AMI430_start_ramping(device_id):
    core.api.device_command(DeviceCommand.AMI430_start_ramping(device_id))

def AMI430_start_rampings(instruments: list[str]):
    for instrument in instruments:
        AMI430_start_ramping(instrument)

def AMI430_pause_ramping(device_id):
    core.api.device_command(DeviceCommand.AMI430_pause_ramping(device_id))

def AMI430_pause_rampings(instruments: list[str]):
    for instrument in instruments:
        AMI430_pause_ramping(instrument)

def AMI430_PSwitch_current(device_id,PSwitch_current):
    core.api.device_command(DeviceCommand.AMI430_PSwitch_current(device_id,PSwitch_current))

def AMI430_PSwitch_ramp_rate(device_id,PSwitch_ramp_rate):
    core.api.device_command(DeviceCommand.AMI430_PSwitch_ramp_rate(device_id,PSwitch_ramp_rate))

def AMI430_PSwitch_heating_time(device_id,PSwitch_heating_time):
    core.api.device_command(DeviceCommand.AMI430_PSwitch_heating_time(device_id,PSwitch_heating_time))

def AMI430_PSwitch_cooling_time(device_id,PSwitch_cooling_time):
    core.api.device_command(DeviceCommand.AMI430_PSwitch_cooling_time(device_id,PSwitch_cooling_time))

def AMI430_PSwitch_cooling_gain(device_id,PSwitch_cooling_gain):
    core.api.device_command(DeviceCommand.AMI430_PSwitch_cooling_gain(device_id,PSwitch_cooling_gain))

def AMI430_stability(device_id,stability):
    """
    :param stability: in percent
    """
    core.api.device_command(DeviceCommand.AMI430_stability(device_id,stability))

def AMI430_set_current_limit(device_id,current_limit):
    """
    :param current_limit: in amperes. The Current Limit is the largest
    magnitude operating current allowed during any ramping mode. For four-
    quadrant power supplies, the Current Limit functions as both a positive
    and negative current limit.
    """
    core.api.device_command(DeviceCommand.AMI430_set_current_limit(device_id,current_limit))

def AMI430_set_voltage_limit(device_id,voltage_limit):
    core.api.device_command(DeviceCommand.AMI430_set_voltage_limit(device_id,voltage_limit))

def AMI430_set_PSwitch_ON(device_id):
    core.api.device_command(DeviceCommand.AMI430_set_PSwitch_ON(device_id))

def AMI430_set_PSwitches_ON(instruments: list[str]):
    for instrument in instruments:
        AMI430_set_PSwitches_ON(instrument)

def AMI430_set_PSwitch_OFF(device_id):
    core.api.device_command(DeviceCommand.AMI430_set_PSwitch_OFF(device_id))

def AMI430_set_PSwitches_OFF(instruments: list[str]):
    for instrument in instruments:
        AMI430_set_PSwitches_OFF(instrument)

def AMI430_set_number_ramp_rate_segment(device_id,nb_segment):
    core.api.device_command(DeviceCommand.AMI430_set_number_ramp_rate_segment(device_id,nb_segment))

def AMI430_set_quench_detect_rate_variable(device_id,variable):
    """
    :param variable: Allowable values are from "0.1" to "2.0"
    """
    core.api.device_command(DeviceCommand.AMI430_set_quench_detect_rate_variable(device_id,variable))

def AMI430_set_quenchDetect(device_id, boolean):
    core.api.device_command(DeviceCommand.AMI430_set_quenchDetect(device_id,boolean))

def AMI430_set_absorber(device_id, boolean):
    """
    :param boolean: Sending “False” indicates that an energy absorber is not present in the system.
    “True” indicates that an energy absorber is present.
    """
    core.api.device_command(DeviceCommand.AMI430_set_absorber(device_id,boolean))

def AMI430_opc(device_id):
    core.api.device_command(DeviceCommand.AMI430_opc(device_id))

def AMI430_rst(device_id):
    """
    Resets the Model 430 Programmer. This is equivalent to cycling the power
    to the Model 430 Programmer using the power switch
    """
    core.api.device_command(DeviceCommand.AMI430_rst(device_id))

def AMI430_remote(device_id):
    """
    disables the front panel controls for purposes of preventing accidental operation of a front
    panel feature
    """
    core.api.device_command(DeviceCommand.AMI430_set_remote(device_id))

def AMI430_local(device_id):
    core.api.device_command(DeviceCommand.AMI430_set_local(device_id))

def AMI430_set_ramp_rate_unit(device_id,time_unit):
    if time_unit == "s":
        unit = False
    elif time_unit == "min":
        unit = True
    else:
        ValueError("The argument should be 's' or 'min'")
    core.api.device_command(DeviceCommand.AMI430_set_ramp_rate_unit(device_id,unit))

def AMI430_set_field_unit(device_id,field_unit):
    if field_unit == "kG":
        unit = False
    elif field_unit == "T":
        unit = True
    else:
        ValueError("The argument should be 'kG' or 'T'")
    core.api.device_command(DeviceCommand.AMI430_set_field_unit(device_id,unit))

def AMI430_get_idn(device_id):
    core.api.device_command(DeviceCommand.AMI430_get_idn(device_id))

def AMI430_reset_quench(device_id):
    core.api.device_command(DeviceCommand.AMI430_reset_quench(device_id))

