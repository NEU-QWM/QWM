from statemachine_commands import *
from state_commands import *
from operation_commands import *

if __name__ == '__main__':
    # Available endpoints for controlling statemachine operations
    list_available_operations_names()
    start_operation('TestProcedure')
    get_running_operation()
