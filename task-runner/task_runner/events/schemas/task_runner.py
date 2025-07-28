"""Schemas of events issued by the task-runner."""
import uuid
from typing import Optional

import task_runner.events.schemas as event_schemas
from task_runner import task_status


# Shared properties of task-runner events.
class TaskRunnerEvent(event_schemas.Event):
    uuid: uuid.UUID


# Task-runner down event.
class TaskRunnerTerminated(TaskRunnerEvent):
    reason: task_status.TaskRunnerTerminationReason
    detail: Optional[str]
    traceback: Optional[str] = None
    stopped_tasks: list[str]
