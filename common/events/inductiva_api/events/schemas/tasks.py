"""Events related to tasks."""
from .event import Event
from inductiva_api.task_status import TaskStatusCode
from uuid import UUID


class TaskEvent(Event):
    id: str
    status: TaskStatusCode


class TaskCreated(TaskEvent):
    method: str
    user_id: int


class TaskInputUploaded(TaskEvent):
    status: TaskStatusCode = TaskStatusCode.SUBMITTED


class TaskStarted(TaskEvent):
    status: TaskStatusCode = TaskStatusCode.STARTED
    executer_id: UUID


class TaskKillRequested(TaskEvent):
    status: TaskStatusCode = TaskStatusCode.PENDING_KILL


class TaskKilled(TaskEvent):
    status: TaskStatusCode = TaskStatusCode.KILLED


class TaskCompleted(TaskEvent):
    pass
