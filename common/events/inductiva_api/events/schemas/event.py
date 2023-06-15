"""Event base class."""
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class Event(BaseModel):
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
