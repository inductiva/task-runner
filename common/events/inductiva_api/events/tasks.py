"""Events related to tasks."""
from .event import Event
from inductiva_api.task_status import TaskStatusCode


class TaskEvent(Event):
    id: str
    status: str


class TaskCreated(TaskEvent):
    method: str
    username: str


class TaskInputUploaded(TaskEvent):
    status: str = TaskStatusCode.SUBMITTED.value


class TaskStarted(TaskEvent):
    status: str = TaskStatusCode.STARTED.value
    executer: str


class TaskKillRequested(TaskEvent):
    status: str = TaskStatusCode.PENDING_KILL.value


class TaskKilled(TaskEvent):
    status: str = TaskStatusCode.KILLED.value


class TaskCompleted(TaskEvent):
    pass


class SpotInstancePreempted(TaskEvent):
    status: str = TaskStatusCode.SPOT_INSTANCE_PREEMPTED.value


class ExecuterTrackerTerminated(TaskEvent):
    status: str = TaskStatusCode.EXECUTER_TERMINATED.value


class ExecuterTrackerFailed(TaskEvent):
    status: str = TaskStatusCode.EXECUTER_FAILED.value
