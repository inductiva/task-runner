from enum import Enum

class TaskStatusCode(Enum):
    PENDING_INPUT = "pending-input"
    SUBMITTED = "submitted"
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    PENDING_KILL = "pending-kill"
    KILLED = "killed"
