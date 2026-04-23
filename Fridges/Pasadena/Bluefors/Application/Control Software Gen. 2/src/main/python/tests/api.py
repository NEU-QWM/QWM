from collections import UserDict
from urllib.error import URLError
from numbers import Number
import builtins

from config import SystemType
from core.device.command import DeviceCommand

class State(UserDict):
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            raise URLError(f"Key {key} not in mocked state in tests")

class TestApi:
    def __init__(self):
        self.state = State()
        self.devices = {}
        self.event_log = []

    def CachingState(self):
        return self.state

    def get(self, key, raises=True):
        try:
            return self.state.get(key)
        except URLError:
            if raises:
                raise

    def get_internal(self, key, raises=True):
        try:
            return self.state.get(key)
        except URLError:
            if raises:
                raise

    def get_parameters(self):
        """
        Returns a normal dictionary, not the mocked URLError raising one.
        """
        return dict(self.state)

    def get_parameter(self, key, raises=True):
        try:
            return self.state.get(key, None)
        except URLError:
            if raises:
                raise

    def get_parameter_types(self):
        def get_type(value):
            match type(value):
                case builtins.str:
                    return "string"
                case builtins.bool:
                    return "bool"
                case _:
                    return "float"
        return {key: get_type(value) for key, value in self.state.items()}


    def set_value(self, key, val):
        self.state[key] = val

    def get_list(self, keys):
        return {key: val for key, val in self.state.items() if key in keys}

    def configured_devices(self):
        return self.state

    def alert(self, alert):
        pass

    def device_command(self, device_command: DeviceCommand, retries=3):
        if device_command.boolean:
            self.devices.setdefault(device_command.device_id, {}).update(
                {"device_on": device_command.enable}
            )

    def statemachine_started(self):
        pass

    def set_name(self, name):
        pass

    def available(self):
        return True

    def persist_operation(self, current_operation, log=False):
        self.state["currentOperation"] = current_operation.serialize()
        if log:
            self.event_log.append(current_operation.serialize())

    def get_system(self):
        return SystemType("python-test")
