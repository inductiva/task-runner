"""Schemas for machine group related events."""

from events import schemas as event_schemas


class MachineGroupCreated(event_schemas.Event):
    uuid: pydantic.UUID
    user_id: str

class MachineGroupStarted(event_schemas.)
