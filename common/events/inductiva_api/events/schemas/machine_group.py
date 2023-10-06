"""Schemas for machine group related events."""
import uuid

from inductiva_api.events import schemas as event_schemas


class MachineGroupCreated(event_schemas.Event):
    uuid: uuid.UUID
    user_id: str
