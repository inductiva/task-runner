# noqa: D104
from .executer import ExecuterTerminationReason
from .task_status import TaskStatusCode

ExecuterTerminationReasonToTaskStatus = {
    ExecuterTerminationReason.INTERRUPTED:
        TaskStatusCode.EXECUTER_TERMINATED,
    ExecuterTerminationReason.VM_PREEMPTED:
        TaskStatusCode.SPOT_INSTANCE_PREEMPTED,
    ExecuterTerminationReason.IDLE_TIMEOUT:
        TaskStatusCode.EXECUTER_TERMINATED,
}
