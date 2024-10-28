from task_runner.operations_logger import OperationsLogger


class ExecCommandLogger:
    """Util class to log operations related to command execution."""

    def __init__(
        self,
        task_id: str,
        operations_logger: OperationsLogger,
    ):
        self._task_id = task_id
        self._operations_logger = operations_logger
        self._operation = None

    def log_command_started(
        self,
        command: str,
        container_command: str,
    ):
        self._operation = self._operations_logger.start_operation(
            name="exec_command",
            task_id=self._task_id,
            attributes={
                "command": command,
                "container_command": container_command,
            },
        )

    def log_command_finished(
        self,
        exit_code: int,
        execution_time_seconds: float,
    ):
        if not self._operation:
            return

        self._operation.end(attributes={
            "exit_code": exit_code,
            "execution_time_s": execution_time_seconds,
        })

        self._operation = None
