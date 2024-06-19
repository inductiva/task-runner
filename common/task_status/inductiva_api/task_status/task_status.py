"""Enum defining the possible task status codes."""
import enum


class TaskStatusCode(enum.Enum):
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
    EXECUTER_TERMINATED_IDLE_TIMEOUT = "executer-terminated-idle-timeout"
    EXECUTER_TERMINATED_TTL_EXCEEDED = "executer-terminated-ttl-exceeded"
    EXECUTER_FAILED = "executer-failed"
    ZOMBIE = "zombie"
    COMPUTATION_STARTED = "computation-started"
    COMPUTATION_ENDED = "computation-ended"
