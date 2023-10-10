"""Events related to tasks."""
from typing import Optional, Dict, Any
import uuid

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


class TaskInputUploaded(TaskEvent):
    input_size_b: int


class TaskPickedUp(TaskEvent):
    machine_id: uuid.UUID
    executer_docker_image_digest: Optional[str] = None
    executer_git_commit_hash: Optional[str] = None


class TaskWorkStarted(TaskEvent):
    machine_id: uuid.UUID


class TaskWorkStartFailed(TaskEvent):
    machine_id: uuid.UUID
    detail: str


class TaskWorkFinished(TaskEvent):
    machine_id: uuid.UUID
    success: bool


class TaskOutputUploaded(TaskEvent):
    machine_id: uuid.UUID
    output_size_b: int


class TaskKillRequested(TaskEvent):
    user_id: int
    current_status: str


class TaskKillCommandIssued(TaskEvent):
    redis_queue: str


class TaskKilled(TaskEvent):
    # optional because the task may have been killed before
    # it was assigned to a machine
    machine_id: Optional[uuid.UUID] = None
