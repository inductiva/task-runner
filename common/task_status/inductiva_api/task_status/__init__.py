# noqa: D104
from .executer import ExecuterTerminationReason
from .task_status import TaskStatusCode

ExecuterTerminationReasonToTaskStatus = {
    ExecuterTerminationReason.INTERRUPTED:
        TaskStatusCode.EXECUTER_TERMINATED,
    ExecuterTerminationReason.VM_PREEMPTED:
        TaskStatusCode.SPOT_INSTANCE_PREEMPTED,
    ExecuterTerminationReason.ERROR:
        TaskStatusCode.EXECUTER_FAILED,
    ExecuterTerminationReason.IDLE_TIMEOUT:
        TaskStatusCode.EXECUTER_TERMINATED,
}
