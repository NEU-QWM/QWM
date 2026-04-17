from pprint import pformat

from lib.colors import Colors, color_text
from lib.http_base import http_get, http_post


def list_available_operations_names():
    op_list = http_get('operations')
    print(f"Available operations are " +
          color_text(f"{list((op.get('name'), op.get('id')) for op in op_list)}", Colors.DARK_BLUE))


def list_available_operations_full():
    op_list = http_get('operations')
    print(f"Full list of operations:\n" + color_text(f"{pformat(op_list)}", Colors.DARK_BLUE))


def get_running_operation():
    running_op = http_get('operations/running')
    print(f"Current running operation is\n" + color_text(f"{pformat(running_op)}", Colors.DARK_BLUE))


def start_operation(operation_name_or_id):
    started_op = http_post(f'operations/{operation_name_or_id}/start')
    print(f"Started operation " +
          color_text(f"{started_op.get('name')} ({started_op.get('id')})", Colors.DARK_BLUE))
