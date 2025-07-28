"""Convert events between dictionary format and right PyDantic model.

"""
import importlib

from .schemas import Event

EVENT_TYPE_KEY = "type"
EVENT_BODY_KEY = "json"
EVENTS_MODULE_NAME = "task_runner.events"


def to_dict(event: Event) -> dict:
    event_json = event.json()
    event_type = event.__class__.__name__

    return {
        EVENT_TYPE_KEY: event_type,
        EVENT_BODY_KEY: event_json,
    }


def from_dict(event_dict: dict) -> Event:
    try:
        event_type = event_dict[EVENT_TYPE_KEY]
        event_json = event_dict[EVENT_BODY_KEY]
    except KeyError as err:
        raise ValueError("Invalid event dictionary.") from err

    events_module = importlib.import_module(EVENTS_MODULE_NAME)
    event_class = getattr(events_module, event_type)

    return event_class.parse_raw(event_json)
