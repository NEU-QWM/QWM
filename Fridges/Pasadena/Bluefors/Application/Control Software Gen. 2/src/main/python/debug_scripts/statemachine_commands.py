from pprint import pformat

from lib.colors import Colors, color_text
from lib.http_base import http_get, http_post


def list_available_statemachines():
    sm_list = http_get('automation')
    print(f"Available statemachines are " + color_text(f"{sm_list}", Colors.DARK_MAGENTA))


def start_statemachine(name):
    # TODO Update this when the CS2Errors are coming
    result = http_post(f'automation/{name}/start')
    if result:
        print(f"Statemachine " + color_text(f"{name}", Colors.DARK_MAGENTA) + " started successfully")
    else:
        print(f"Starting statemachine " + color_text(f"{name}", Colors.DARK_MAGENTA) + " failed")


def get_running_statemachine():
    sm_state = http_get(f'internal/automation/state')
    print(f"Statemachine full state is\n" + color_text(f"{pformat(sm_state)}", Colors.DARK_MAGENTA))


def get_running_statemachine_name():
    name = http_get(f'internal/automation/name')
    print(f"Statemachine " + color_text(f"{name}", Colors.DARK_MAGENTA) + " is currently running")


def get_running_statemachine_simplified():
    params = {'keys': 'name,'
                      'values.currentOperation.name,'
                      'values.currentOperation.currentProcedure'}
    res = http_get(f'internal/state', params)
    print(f"Currently running statemachine " +
          color_text(f"{res.get('name')}", Colors.DARK_MAGENTA) + ", "
          f"current operation is " +
          color_text(f"{res.get('values.currentOperation.name')}", Colors.DARK_MAGENTA) + " "
          f"and current procedure is " +
          color_text(f"{res.get('values.currentOperation.currentProcedure')}", Colors.DARK_MAGENTA) + ".")
