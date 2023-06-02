"""Definition of constants related to the executers."""
from enum import Enum


class ExecuterTerminationReason(Enum):
    INTERRUPTED = "interrupted"
    VM_PREEMPTED = "preempted"
    ERROR = "error"
