"""Event base class."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Event(BaseModel):
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
