"""Events related to tasks."""
from .event import Event


class TaskEvent(Event):
    id: str
    status: str


class TaskCreated(TaskEvent):
    method: str
    username: str


class TaskInputUploaded(TaskEvent):
    status: str = "submitted"


class TaskStarted(TaskEvent):
    status: str = "started"
    executer: str


class TaskKillRequested(TaskEvent):
    status: str = "pending-kill"


class TaskKilled(TaskEvent):
    status: str = "killed"


class TaskCompleted(TaskEvent):
    pass


class SpotInstancePreempted(TaskEvent):
    status: str = "spot-instance-preempted"


class ExecuterTrackerTerminated(TaskEvent):
    status: str = "executer-tracker-terminated"


class ExecuterTrackerFailed(TaskEvent):
    status: str = "executer-tracker-failed"
