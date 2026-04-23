"""
Delayed API calls to devices.

Additionally checks if a device is enabled before sending the command, and does
not execute redundant calls (e.g. turning on a device that is already on).

Currently supports only heaters, valves and pumps.
"""

from typing import List, Dict

import core.api
from core.device.command import DeviceCommand
from core.state_machine.exceptions import ProcedureError
from sm.general.helpers import Helpers


class CommandQueue:
    supported_actions = ["heaterOnOff", "valveOnOff", "pumpStartStop"]

    def __init__(self):
        self.heater_commands: List[DeviceCommand] = []
        self.valve_commands: List[DeviceCommand] = []
        self.pump_commands: List[DeviceCommand] = []

    def __repr__(self):
        return (
            f"Enables pumps: {[c.device_id for c in self.pump_commands if c.enable]}\n"
            f"Disables pumps: {[c.device_id for c in self.pump_commands if not c.enable]}\n"
            f"Enables valves: {[c.device_id for c in self.valve_commands if c.enable]}\n"
            f"Disables valves: {[c.device_id for c in self.valve_commands if not c.enable]}\n"
            f"Enables heaters: {[c.device_id for c in self.heater_commands if c.enable]}\n"
            f"Disables heaters: {[c.device_id for c in self.heater_commands if not c.enable]}"
        )

    @property
    def empty(self):
        return self.heater_commands == self.valve_commands == self.pump_commands == []

    def set_state(self, state: Dict[str, list[str]]):
        valves = state.get("valves", [])
        valves_off = set(Helpers.all_valves) - set(valves)
        self.queue_valves_off(list(valves_off))
        self.queue_valves_on(valves)

        pumps = state.get("pumps", [])
        pumps_off = set(Helpers.all_pumps) - set(pumps)
        self.queue_pumps_off(list(pumps_off))
        self.queue_pumps_on(pumps)

    def execute_queued_commands(self):
        for queue in [self.heater_commands, self.valve_commands, self.pump_commands]:
            execute_queue(queue)
            queue.clear()

    def queue_valves_on(self, valves: list):
        for valve in valves:
            self.valve_commands.append(DeviceCommand.valve_on(device_id=valve))

    def queue_valves_off(self, valves: list):
        for valve in valves:
            self.valve_commands.append(DeviceCommand.valve_off(device_id=valve))

    def queue_pumps_on(self, pumps: list):
        for pump in pumps:
            self.pump_commands.append(DeviceCommand.pump_on(device_id=pump))

    def queue_pumps_off(self, pumps: list):
        for pump in pumps:
            self.pump_commands.append(DeviceCommand.pump_off(device_id=pump))

    def queue_heaters_on(self, heaters: list):
        for heater in heaters:
            self.heater_commands.append(DeviceCommand.heater_on(device_id=heater))

    def queue_heaters_off(self, heaters: list):
        for heater in heaters:
            self.heater_commands.append(DeviceCommand.heater_off(device_id=heater))


def execute_queue(queue: List[DeviceCommand]):
    enabled = core.api.get_list([f"{d.device_id}_ENABLED" for d in queue])

    for device_command in queue:
        if device_command.device_id in core.api.configured_devices():
            try:
                device_enabled = enabled[f"{device_command.device_id}_ENABLED"]
            except KeyError:
                raise ProcedureError(message=f"Failed getting value for {f'{device_command.device_id}_ENABLED'}")

            if device_enabled and not device_command.enable:
                core.api.device_command(device_command)

            elif not device_enabled and device_command.enable:
                core.api.device_command(device_command)

            # Include the no-op cases just for clarity
            elif device_enabled and device_command.enable:
                continue

            elif not device_enabled and not device_command.enable:
                continue
