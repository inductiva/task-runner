"""Definition of constants related to the task-runner."""
from enum import Enum


class TaskRunnerTerminationReason(Enum):
    INTERRUPTED = "interrupted"
    VM_PREEMPTED = "preempted"
    ERROR = "error"
    IDLE_TIMEOUT = "idle_timeout"
