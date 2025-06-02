"""Functions to perform cleanup when the task-runner is terminated."""
import signal
import sys
import threading
import traceback

from absl import logging
from inductiva_api import events
from inductiva_api.task_status import TaskRunnerTerminationReason

import task_runner


class TaskRunnerTerminationError(Exception):
    """Exception raised when the task-runner is terminated."""

    def __init__(self, reason, detail=None):
        self.reason = reason
        self.detail = detail

    def __str__(self):
        return f"TaskRunnerTerminationError({self.reason}, {self.detail})"


class ScaleDownTimeoutError(TaskRunnerTerminationError):
    """Exception raised when the timeout is reached,
    and the Machine Group is scaled down."""

    def __init__(self):
        super().__init__(TaskRunnerTerminationReason.IDLE_TIMEOUT)


class TerminationHandler:

    def __init__(
        self,
        task_runner_id,
        request_handler,
    ):
        self.task_runner_id = task_runner_id
        self.request_handler = request_handler
        self._lock = threading.Lock()
        self._termination_logged = False

        api_client = task_runner.ApiClient.from_env()
        self.event_logger = task_runner.WebApiLogger(
            api_client=api_client,
            task_runner_id=task_runner_id,
        )

    def log_termination(self,
                        reason,
                        detail=None,
                        save_traceback=False) -> bool:
        """Logs the termination of the task-runner.

        This method should be called when the task-runner is terminated.
        It logs the termination event, using internal state to ensure that the
        event is only logged once.

        Returns:
            True if the termination event was successfully logged, False
            if the log was skipped because it was already logged.
        """
        with self._lock:
            if self._termination_logged:
                logging.info("Another thread already started "
                             "termination logging. Skipping...")
                return False

            self._termination_logged = True

        stopped_tasks = []
        if self.request_handler.is_task_running():
            logging.info("Task was being executed: %s.",
                         self.request_handler.task_id)
            self.request_handler.interrupt_task()
            stopped_tasks.append(self.request_handler.task_id)

        self.request_handler.set_shutting_down()
        traceback_str = traceback.format_exc() if save_traceback else None

        event = events.TaskRunnerTerminated(
            uuid=self.task_runner_id,
            reason=reason,
            stopped_tasks=stopped_tasks,
            detail=detail,
            traceback=traceback_str,
        )
        self.event_logger.log(event)

        # if self.request_handler.is_task_running():
        #     self.request_handler.save_output(force=True)

        logging.info("Successfully logged task-runner termination.")

        return True


def get_signal_handler(termination_handler):

    def handler(signum, _):
        logging.info("Caught signal %s.", signal.Signals(signum).name)

        reason = TaskRunnerTerminationReason.INTERRUPTED

        logged_termination = termination_handler.log_termination(reason)
        if logged_termination:
            sys.exit()

    return handler


def setup_cleanup_handlers(termination_handler):

    signal_handler = get_signal_handler(termination_handler)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
