from json import JSONDecodeError

import requests

from debug_scripts.lib.colors import color_text, Colors

base_url = "http://localhost:8082"  # Base URL for CS2 backend


def _check_cs2_backend_running():
    def print_error():
        print(color_text(" ERROR ", Colors.DARK_RED_BACKGROUND + Colors.BOLD) + ": " +
              color_text(f"CS2 backend not running at {base_url}", Colors.DARK_RED))

    try:
        response = requests.get(base_url)
        if response.status_code != 200:
            print_error()
    except (Exception,):
        print_error()


def _parse_response(response):
    if response.status_code == 405:
        print(f"Method not allowed {response.url}")
        return None

    if content_type := response.headers.get('Content-Type'):
        if 'application/json' in content_type:
            try:
                return response.json()
            except JSONDecodeError:
                # It is possible for the CS2 to return data which is not a valid JSON, despite it being marked as such
                return response.content.decode()
        else:
            print(f"Request failed with {response.status_code} {response.reason}")
    return None


def http_get(endpoint, params=None):
    _check_cs2_backend_running()
    return _parse_response(requests.get(f'{base_url}/{endpoint}', params))


def http_post(endpoint, params=None):
    _check_cs2_backend_running()
    return _parse_response(requests.post(f'{base_url}/{endpoint}', params))
