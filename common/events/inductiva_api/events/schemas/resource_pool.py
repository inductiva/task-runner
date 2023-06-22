"""Schema for resource pool related events."""
from uuid import UUID

from .event import Event


class ResourcePoolCreated(Event):
    uuid: UUID
    created_by: str
