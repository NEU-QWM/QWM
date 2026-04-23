# This module is exposed to the Java side of the CS2 system.
import logging

from configuration.hardware import sentinel_parameters
import core.api
import sm.automation_test.statemachine
import sm.dilution_systems.statemachine
import sm.FSE.statemachine
import sm.helium_systems.statemachine
import sm.manual.statemachine
import sm.milestone_a.statemachine
import sm.sentinel_test.statemachine
import sm.simple.statemachine
from core.handlers import JavaLoggingHandler, SentinelHandler, StateMachineHandler
from configuration.hardware.graphs import device_graphs
import config

logger = logging.getLogger(__name__)
root_logger = logging.getLogger()
# root_logger.setLevel(logging.DEBUG)

config_modules = {
    "manual": sm.manual.statemachine,
    "simple": sm.simple.statemachine,
    "milestone-a": sm.milestone_a.statemachine,
    "sentinel-test": sm.sentinel_test.statemachine,
    "dilution-systems": sm.dilution_systems.statemachine,
    "helium-systems": sm.helium_systems.statemachine,
    "automation-test": sm.automation_test.statemachine,
    "fse": sm.FSE.statemachine,
}

# Initialize the handler with some statemachine when module is imported -- but
# only start it when the real requested statemachine is set via sm_start
handler = StateMachineHandler(None)
sentinel_handler = SentinelHandler()


# The following functions need to be provided:
def set_logger_service(service):
    root = logging.getLogger()
    root.handlers.clear()

    handler = JavaLoggingHandler(service)

    root.addHandler(handler)
    root.setLevel(logging.DEBUG)  # Logs below level INFO might be filtered out on Java side?
    logging.debug("Logging handler initialized")


def set_api_base_url(url):
    core.api.api_url = url


def set_authentication_client_configuration(realm, auth_server_url, client_id, client_secret):
    core.api.auth = core.api.KeycloakAuthConfig(auth_server_url, client_id, realm, client_secret)


def module_reload_statemachines():
    pass


def list_automations(*args, **kwargs):
    return list(config_modules.keys())


def start_automation(name, start=True):
    try:
        config_module = config_modules[name]
        system_type = core.api.get_system()
        parameters = core.api.get_parameters()
        device_graph = device_graphs[system_type]
        automation_config = config.AutomationConfig(name, config_module, system_type, parameters, device_graph)
    except KeyError:
        logging.error(f"State machine with name {name} does not exist")
        raise AttributeError(f"State machine with name {name} does not exist")

    try:
        handler.start(automation_config, start)
        sentinel_handler.start(automation_config)
    except Exception:
        logging.exception(f"Unexpected exception trying to start state machine")
        raise


def stop_automation(skip_if_not_running=False):
    handler.stop(skip_if_not_running)
    sentinel_handler.stop()


def check_with_sentinel_and_sentry(new_state: dict):
    logging.debug(f"Gateway: check with sentinel and sentry {new_state}")
    return sentinel_handler.check(new_state)


def check_with_sentinel(new_state: dict, change: dict):
    logging.debug(f"Gateway: check with sentinel {new_state}")
    return sentinel_handler.check_with_sentinel(new_state, change)


def start_operation(operation_name_or_id, parameters, include_validations=False):
    logging.debug(f"Gateway: start_operation {operation_name_or_id}, {parameters}")
    return handler.start_operation(operation_name_or_id, parameters, include_validations)


def get_operations(include_validations=False):
    logging.debug("Gateway: get_operations")
    return handler.get_operations(include_validations)


def get_operation(name_or_id):
    logging.debug(f"Gateway: get_operation {name_or_id}")
    return handler.get_operation(name_or_id)


def get_operation_parameters(name_or_id):
    logging.debug(f"Gateway: get_operation_parameters {name_or_id}")
    return handler.get_operation_parameters(name_or_id)


def get_running_operation():
    logging.debug("Gateway: get_running_operation")
    return handler.get_running_operation()


def get_procedure_graph():
    logging.debug("Gateway: get_operations")
    return handler.get_procedure_graph()
