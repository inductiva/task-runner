"""Events related to tasks."""
import uuid
from typing import Any, Dict, Optional

import inductiva_api.events.schemas as event_schemas


class TaskEvent(event_schemas.Event):
    id: str


class TaskCreated(TaskEvent):
    user_id: int
    api_method_name: str
    machine_group_id: uuid.UUID
    scenario_name: Optional[str]
    client_version: Optional[str]
    request_params: Dict[str, Any]
    task_storage_dir: str


class TaskInputUploaded(TaskEvent):
    input_size_b: int = 0


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


class TaskKillRequested(TaskEvent):
    user_id: int
    current_status: str


class TaskKillCommandIssued(TaskEvent):
    redis_queue: str


class TaskKilled(TaskEvent):
    # optional because the task may have been killed before
    # it was assigned to a machine
    machine_id: Optional[uuid.UUID] = None


class TaskExecutionFailed(TaskEvent):
    error_message: str
    machine_id: uuid.UUID
