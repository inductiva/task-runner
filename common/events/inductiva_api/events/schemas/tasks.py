"""Events related to tasks."""
from typing import Optional, Dict, Any
import uuid

import inductiva_api.events.schemas as event_schemas


class TaskEvent(event_schemas.Event):
    id: str


class TaskCreated(TaskEvent):
    method: str
    user_id: int
    machine_group_id: uuid.UUID
    scenario_name: Optional[str]
    client_version: str
    request: Dict[str, Any]


class TaskInputUploaded(TaskEvent):
    input_size_b: int


class TaskPickedUp(TaskEvent):
    machine_id: uuid.UUID
    executer_docker_image_digest: Optional[str] = None
    executer_git_commit_hash: Optional[str] = None


class TaskWorkStarted(TaskEvent):
    machine_id: uuid.UUID


class TaskWorkFinished(TaskEvent):
    machine_id: uuid.UUID


class TaskOutputUploaded(TaskEvent):
    machine_id: uuid.UUID
    output_size_b: int


class TaskKillRequested(TaskEvent):
    user_id: int


class TaskKilled(TaskEvent):
    machine_id: uuid.UUID


class TaskCompleted(TaskEvent):
    machine_id: uuid.UUID
    success: bool
