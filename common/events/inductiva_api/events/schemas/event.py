"""Event base class."""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    elapsed_time_s: Optional[float] = Field(default=None)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
