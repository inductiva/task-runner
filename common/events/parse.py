"""Convert events between dictionary format and right PyDantic model.

"""
import importlib
from datetime import datetime
from .event import Event

# Key used to store event type when converting object to dictionary,
# used to construct right PyDantic model when converting back to object.
EVENT_TYPE_KEY = "__type__"
EVENT_TO_DICT_CONFIG = {
    # Custom functions to convert fields of specific types
    # when converting object to dict.
    datetime: lambda v: v.timestamp(),
}
EVENTS_MODULE_NAME = "inductiva_api.events"


def to_dict(event: Event) -> dict:
    event_dict = event.dict()

    for key, value in event_dict.items():
        if EVENT_TO_DICT_CONFIG.get(type(value)):
            event_dict[key] = EVENT_TO_DICT_CONFIG[type(value)](value)

    event_dict[EVENT_TYPE_KEY] = event.__class__.__name__

    return event_dict


def from_dict(event_dict: dict) -> Event:
    event_type = event_dict.pop(EVENT_TYPE_KEY)
    events_module = importlib.import_module(EVENTS_MODULE_NAME)
    event_class = getattr(events_module, event_type)
    return event_class(**event_dict)
