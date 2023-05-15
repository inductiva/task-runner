"""Events related to tasks."""
from .event import Event


class TaskEvent(Event):
    id: str
    status: str


class TaskCreated(TaskEvent):
    method: str
    username: str


class TaskInputUploaded(TaskEvent):
    pass


class TaskStarted(TaskEvent):
    executer: str


class TaskKillRequested(TaskEvent):
    pass


class TaskKilled(TaskEvent):
    pass


class TaskCompleted(TaskEvent):
    pass
