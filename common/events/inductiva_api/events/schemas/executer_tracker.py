"""Schemas of events issued by the executer-tracker."""
import uuid
from typing import List, Optional

import inductiva_api.events.schemas as event_schemas
from inductiva_api import task_status


# Shared properties of executer tracker events.
class ExecuterTrackerEvent(event_schemas.Event):
    uuid: uuid.UUID


# Executer tracker down event.
class ExecuterTrackerTerminated(ExecuterTrackerEvent):
    reason: task_status.ExecuterTerminationReason
    detail: Optional[str]
    stopped_tasks: List[str]
