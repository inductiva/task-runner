import uuid

from inductiva_api import events

import task_runner


class CommandEventLogger:

    def __init__(
        self,
        task_id: str,
        machine_id: uuid.UUID,
        event_logger: task_runner.BaseEventLogger,
    ):
        self.task_id = task_id
        self.machine_id = machine_id
        self.event_logger = event_logger

    def log_command_started(
        self,
        command: str,
        apptainer_command: str,
    ):
        event = events.TaskCommandStarted(
            id=self.task_id,
            machine_id=self.machine_id,
            command=command,
            container_command=apptainer_command,
        )
        self.event_logger.log(event)

    def log_command_finished(
        self,
        command: str,
        exit_code: int,
        execution_time: float,
    ):
        event = events.TaskCommandFinished(
            id=self.task_id,
            machine_id=self.machine_id,
            command=command,
            exit_code=exit_code,
            execution_time=execution_time,
        )
        self.event_logger.log(event)
