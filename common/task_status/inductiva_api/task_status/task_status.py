"""Enum defining the possible task status codes."""
from enum import StrEnum


class TaskStatusCode(StrEnum):
    """Possible task status codes."""
    PENDING_INPUT = "pending-input"
    SUBMITTED = "submitted"
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    PENDING_KILL = "pending-kill"
    KILLED = "killed"
    SPOT_INSTANCE_PREEMPTED = "spot-instance-preempted"
    EXECUTER_TERMINATED = "executer-terminated"
    EXECUTER_TERMINATED_BY_USER = "executer-terminated-by-user"
    EXECUTER_FAILED = "executer-failed"
    ZOMBIE = "zombie"
    COMPUTATION_STARTED = "computation-started"
    COMPUTATION_ENDED = "computation-ended"
