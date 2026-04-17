
# --- imports
import logging

from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def serialize(obj):
    if obj is None:
        return obj
    elif isinstance(obj, list):
        return [serialize(s) for s in obj]
    elif isinstance(obj, dict):
        result = dict(**obj)
        for key, value in result.items():
            result[key] = serialize(value)
        return result
    elif isinstance(obj, datetime):
        return obj.isoformat().replace('+00:00', 'Z')
    elif isinstance(obj, timedelta):
        return obj.total_seconds()
    elif isinstance(obj, type):
        return obj.__name__
    return obj


def deserialize(obj, key=None):
    logger.debug('deserialize(type: %s) %s, (key %s)', obj.__class__.__name__, obj, key)
    if obj is None:
        return obj
    elif isinstance(obj, list) or obj.__class__.__name__ == 'jvm-list-as-python':
        return [deserialize(s) for s in obj]
    elif isinstance(obj, dict) or obj.__class__.__name__ == 'jvm-map-as-python':
        if obj.keys() is None:
            logger.warning('Not serializing dict with non-iterable keyset: %s', obj)
            return obj

        result = dict(**obj)
        for key, value in result.items():
            result[key] = deserialize(value, key)
        return result
    elif key and key.endswith('Datetime'):
        try:
            return datetime.fromisoformat(obj)
        except ValueError:
            return datetime.fromisoformat(obj.replace('Z', '+00:00'))
    elif isinstance(key, (int, float)) and key.endswith('Timedelta'):
        return timedelta(seconds=obj)
    return obj


def tznow():
    return datetime.now(timezone.utc)


def check_parameter_type(value, configuration_type):
    """
    See AutomationConfiguration.java for possible types
    """
    if configuration_type == "float":
        return type(value) in (float, int)
    elif configuration_type == "int":
        return type(value) is int
    elif configuration_type == "bool":
        return type(value) is bool
    elif configuration_type == "string":
        return type(value) is str
