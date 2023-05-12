"""Events related to tasks."""
from .event import Event


class TaskEvent(Event):
    id: str


class TaskCreation(TaskEvent):
    method: str
    username: str


class TaskInputUpload(TaskEvent):
    pass


class TaskStart(TaskEvent):
    executer: str


class TaskKilled(TaskEvent):
    pass


class TaskCompletion(TaskEvent):
    status: str
