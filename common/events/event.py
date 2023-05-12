"""Event base class."""
from pydantic import BaseModel, Field
from datetime import datetime


class Event(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
