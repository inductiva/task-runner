"""Events related to tasks."""
import uuid
from typing import Optional

import inductiva_api.events.schemas as event_schemas


class TaskEvent(event_schemas.Event):
    id: str


class TaskPickedUp(TaskEvent):
    machine_id: uuid.UUID
    executer_docker_image_digest: Optional[str] = None
    executer_git_commit_hash: Optional[str] = None


class TaskWorkStarted(TaskEvent):
    machine_id: uuid.UUID


class TaskWorkFinished(TaskEvent):
    machine_id: uuid.UUID


class TaskOutputUploaded(TaskEvent):
    new_status: str
    machine_id: uuid.UUID
    # Output size in bytes, it's optional because the output may not be
    # available when the event is emitted by the executer tracker
    output_size: Optional[int] = None


class TaskKilled(TaskEvent):
    # optional because the task may have been killed before
    # it was assigned to a machine
    machine_id: Optional[uuid.UUID] = None


class TaskExecutionFailed(TaskEvent):
    error_message: str
    machine_id: uuid.UUID
    traceback: Optional[str] = None


class TaskCommandStarted(TaskEvent):
    machine_id: uuid.UUID
    command: str
    container_command: str


class TaskCommandFinished(TaskEvent):
    machine_id: uuid.UUID
    command: str
    exit_code: int
    execution_time: float
