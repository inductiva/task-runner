"""Events related to tasks."""
import datetime
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


class TaskOutputStalled(TaskEvent):
    machine_id: uuid.UUID
    last_modified_file_path: str
    last_modified_file_timestamp: datetime.datetime


class TaskOutputUploaded(TaskEvent):
    machine_id: uuid.UUID
    new_status: Optional[str] = None


class TaskOutputUploadFailed(TaskEvent):
    machine_id: uuid.UUID
    error_message: str
    traceback: Optional[str] = None


class TaskKilled(TaskEvent):
    # optional because the task may have been killed before
    # it was assigned to a machine
    machine_id: Optional[uuid.UUID] = None


class TaskExecutionFailed(TaskEvent):
    error_message: str
    machine_id: uuid.UUID
    traceback: Optional[str] = None
