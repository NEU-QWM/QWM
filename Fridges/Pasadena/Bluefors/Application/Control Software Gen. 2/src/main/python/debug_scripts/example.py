from statemachine_commands import *
from state_commands import *
from operation_commands import *

if __name__ == '__main__':
    print(color_text("--- STATEMACHINE ENDPOINTS ---", Colors.BRIGHT_MAGENTA))
    # Available endpoints for controlling statemachines
    list_available_statemachines()
    start_statemachine('simple')
    get_running_statemachine_name()
    get_running_statemachine_simplified()
    get_running_statemachine()

    print()
    print(color_text("--- OPERATION ENDPOINTS ---", Colors.BRIGHT_BLUE))
    # Available endpoints for controlling statemachine operations
    list_available_operations_names()
    start_operation('TestProcedure')
    get_running_operation()
    list_available_operations_full()
    get_running_operation()
    start_operation('StartSystem')
    get_running_operation()

    print()
    print(color_text("--- STATE ENDPOINTS ---", Colors.BRIGHT_GREEN))
    # Available endpoints for getting values or mappings from the state
    get_from_state('P1')
    get_from_state('P1_PRESSURE')
