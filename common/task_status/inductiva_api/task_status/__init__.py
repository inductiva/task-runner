# noqa: D104
from .executer import TaskRunnerTerminationReason
from .task_status import TaskStatusCode

TaskRunnerTerminationReasonToTaskStatus = {
    TaskRunnerTerminationReason.INTERRUPTED:
        TaskStatusCode.EXECUTER_TERMINATED,
    TaskRunnerTerminationReason.VM_PREEMPTED:
        TaskStatusCode.SPOT_INSTANCE_PREEMPTED,
    TaskRunnerTerminationReason.IDLE_TIMEOUT:
        TaskStatusCode.EXECUTER_TERMINATED,
}
