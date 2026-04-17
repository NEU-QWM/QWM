from pprint import pformat

from lib.colors import Colors, color_text
from lib.http_base import http_get


def get_from_state(key):
    value = http_get(f'state/{key}')
    if value:
        print("Value of " + color_text(key, Colors.DARK_GREEN) + " is " + color_text(pformat(value), Colors.DARK_GREEN))
    else:
        print("State was given unknown key " + color_text(key, Colors.BRIGHT_RED))
