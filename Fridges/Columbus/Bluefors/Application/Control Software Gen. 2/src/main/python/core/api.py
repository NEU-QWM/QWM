from __future__ import annotations

import ssl
import json
import logging
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import cache
from typing import TYPE_CHECKING, overload
from urllib import request
from urllib.error import HTTPError, URLError

from configuration.hardware import SystemType
from core import utils
from core.device.command import AlertCommand, AlertSeverity, DeviceCommand, StateMachineError
from core.mappings import BooleanMappings, DictMappings, NumericMappings

if TYPE_CHECKING:
    from core.state_machine.operation import RunningOperation

# Overwritten by automation startup
api_url = "http://localhost:8082/api/v1"
auth = None


@dataclass
class KeycloakAuthConfig:
    server_url: str
    client_id: str
    realm_name: str
    client_secret_key: str
    expiry: datetime = field(default_factory=utils.tznow)

    def __post_init__(self):
        self.server_url = self.server_url.rstrip("/")
        self.token = None

    @property
    def openid_auth_url(self):
        return f"{self.server_url}/realms/{self.realm_name}/protocol/openid-connect/token"

    @property
    def post_data(self):
        return {
            "grant_type": "client_credentials",
            "client_secret": self.client_secret_key,
            "client_id": self.client_id,
            "scope": "openid",
        }

    @staticmethod
    def _post(url, data):
        d = urllib.parse.urlencode(data)
        # TODO: add certificate instead of disabling it
        myssl = ssl.create_default_context()
        myssl.check_hostname = False
        myssl.verify_mode = ssl.CERT_NONE
        res = request.urlopen(request.Request(url, method="POST", data=d.encode("utf-8"), headers={}), context=myssl)
        return json.load(res)

    @property
    def expired(self):
        return utils.tznow() >= self.expiry

    def get_auth_token(self):
        if self.token is None or self.expired:
            self.id = self._post(self.openid_auth_url, self.post_data)
            self.token = self.id["access_token"]
            self.expiry = utils.tznow() + timedelta(seconds=self.id.get("expires_in", 0) - 1)

        return f"Bearer {self.token}"


class Endpoints(Enum):
    alert = "alerts/raise"
    automation_events = "internal/automation/events"
    devices = "state/devices"
    error = "internal/automation/error"
    internal = "internal/automation/values"
    parameters = "internal/automation/parameters"
    set_name = "internal/automation/name"
    signal_running = "internal/automation/running"
    system = "system"
    configuration = "configuration"
    mappings = "configuration/mappings"
    state = "state"

    def __format__(self, spec):
        return f"{self.value}"


logger = logging.getLogger(__name__)


def retry(req: request.Request, retries=1, parse_json=True):
    for i in range(retries):
        if auth is not None:
            req.add_header("Authorization", auth.get_auth_token())
        try:
            with request.urlopen(req) as response:
                if parse_json:
                    return json.load(response)
                return response
        except URLError:
            if i == retries - 1:
                raise
    raise


class State:
    """
    Simple wrapper around API, just to provide the syntax:
     - state["value"]
     - "value" in state

    For setting values, use api.set or other relevant method.
    """

    def get(self, key, default):
        if (value := get(key, raises=False)) is not None:
            return value

        return default

    def _get(self, key, raises=True):
        return get(key, raises)

    def __contains__(self, key):
        return self._get(key, raises=False) is not None

    # These can be used to enable type hints when writing procedures, so you
    # don't end up doing something like state["V001_ENABLED"] > 3.0
    @overload
    def __getitem__(self, key: NumericMappings) -> float: ...

    @overload
    def __getitem__(self, key: BooleanMappings) -> bool: ...

    @overload
    def __getitem__(self, key: DictMappings) -> dict: ...

    def __getitem__(self, key):
        return self._get(key)


# Instantiate here, import with 'from core.api import state'
state = State()


class CachingState(State):
    """
    Used in operation/procedure validations.

    Especially from Manual mode, there are can be ~500 possible paths
    (operations). Done naively, this will results in hundreds of calls over
    HTTP to fetch the same few variables used in procedure/operation
    validations.

    This is used to cache variables for a single get_operations call.
    """

    def __init__(self):
        self.cache = {}

    def _get(self, key, raises=True):
        if key not in self.cache:
            self.cache[key] = get(key, raises)
        return self.cache[key]


def _get(url) -> dict:
    return retry(request.Request(url), 3, parse_json=True)


def _post(url, payload, retries=3):
    try:
        response = retry(
            request.Request(
                url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(utils.serialize(payload)).encode("utf-8"),
                method="POST",
            ),
            retries=retries,
            parse_json=False,
        )
        if response.status not in (200, 201):
            logging.error("Failed setting value through API")
    except HTTPError as e:
        body = e.read().decode()
        logger.info(f"Error posting payload {payload}, error body: {body}")
        logger.debug(f"api._post HTTPError {e.status} {e.msg}")
        raise

    except URLError:
        logger.error(f"api._post URLError {url}")
        raise


def get(key, raises=True):
    try:
        value = _get(f"{api_url}/{Endpoints.devices}/{key}")
        return utils.deserialize(value, key)
    except URLError:
        if raises:
            raise


def get_internal(key, raises=True):
    try:
        value = _get(f"{api_url}/{Endpoints.internal}/{key}")
        return utils.deserialize(value, key)
    except URLError:
        if raises:
            raise


def get_parameters():
    return _get(f"{api_url}/{Endpoints.parameters}")


def get_parameter(key, raises=True):
    try:
        return _get(f"{api_url}/{Endpoints.parameters}/{key}")
    except URLError:
        if raises:
            raise


def get_parameter_types():
    try:
        parameters = _get(f"{api_url}/{Endpoints.configuration}")
        return {p["id"]: p["type"] for p in parameters["automation"]["settings"]}
    except URLError:
        raise


def set_value(key, value):
    _post(f"{api_url}/{Endpoints.internal}/{key}", value)


def get_list(keys):
    param = urllib.parse.urlencode({"keys": ",".join(keys)})
    response = _get(f"{api_url}/{Endpoints.devices}?{param}")
    values = utils.deserialize(response)

    return values


@cache
def configured_devices():
    """
    Device calls from StateMachine will only use those defined in mappings.yaml
    """
    devices = set()
    try:
        config = _get(f"{api_url}/{Endpoints.configuration}")

        disabled_devices = {id for id, device in config["devices"].items() if not device["enabled"]}
        devices = set(config["mappings"].keys())

        for key, value in config["mappings"].items():
            # Remove mapping like
            #    HEATER:    bftc-device-2.heaters.1
            # from configured devices, if the parent bftc-device-2 is disabled
            if any(root in value for root in disabled_devices):
                devices.discard(key)

    except URLError:
        raise Exception("Failed to fetch configured devices when starting state machine")
    return devices


def device_command(device_command: DeviceCommand, skip_missing=True, retries=3):
    """
    Procedures are written assuming a superset of possible devices, and they
    include commands to devices that might not exist on the actual system. In
    the normal case, those commands can be safely ignored.
    """
    if skip_missing:
        if device_command.device_id not in configured_devices():
            logger.debug(f"Skipping device call to {device_command.device_id} not found in configured devices")
            return
    _device_command(device_command, retries)


def _device_command(device_command: DeviceCommand, retries=3):
    _post(f"{api_url}/devices/{device_command.device_id}/command", device_command.format(), retries)


def statemachine_started():
    _post(f"{api_url}/{Endpoints.signal_running}", "")


def alert(alert_command: AlertCommand):
    try:
        _post(f"{api_url}/{Endpoints.alert}", alert_command.format())
    except URLError:
        pass


def error(error: StateMachineError):
    _post(f"{api_url}/{Endpoints.error}", error.format())


def set_name(name):
    _post(f"{api_url}/{Endpoints.set_name}", {"name": name})


def available():
    try:
        _ = _get(f"{api_url}/{Endpoints.state}")
    except HTTPError as e:
        body = e.read().decode()
        message = json.loads(body)
        if message["state"] == "STARTING":
            return False
    return True


def persist_operation(current_operation: RunningOperation, log=False):
    try:
        set_value("currentOperation", current_operation.serialize())
        if log:
            _post(f"{api_url}/{Endpoints.automation_events}", current_operation.serialize_to_automation_event())
    except URLError:
        alert(AlertCommand(AlertSeverity.WARNING, 1649, "Failed persisting current operation", "Automation error"))
    if log:
        try:
            device_command(DeviceCommand.broadcast_cs2_state(current_operation), retries=1)
        except URLError:
            logger.debug("Failed persisting operation info to PLC")


def get_system():
    return SystemType(_get(f"{api_url}/{Endpoints.system}").get("systemType"))
