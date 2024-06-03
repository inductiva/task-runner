"""Functions to perform cleanup when the executer tracker is terminated."""
import signal
import sys

from absl import logging

import executer_tracker
from executer_tracker import redis_utils
from executer_tracker.utils import gcloud
from inductiva_api import events
from inductiva_api.task_status import ExecuterTerminationReason


class TerminationHandler:

    def __init__(
        self,
        executer_id,
        local_mode,
        redis_hostname,
        redis_port,
        request_handler,
    ):
        self.executer_id = executer_id
        self.request_handler = request_handler

        if local_mode:
            api_client = executer_tracker.ApiClient.from_env()
            self.event_logger = executer_tracker.WebApiLogger(
                api_client=api_client,
                executer_tracker_id=executer_id,
            )
        else:
            self.event_logger = executer_tracker.RedisEventLogger(
                connection=redis_utils.create_redis_connection(
                    redis_hostname, redis_port))

    def log_termination(self, reason, detail=None):

        stopped_tasks = []
        if self.request_handler.is_task_running():
            logging.info("A task was being executed.")
            stopped_tasks.append(self.request_handler.task_id)

        self.event_logger.log(
            events.ExecuterTrackerTerminated(
                uuid=self.executer_id,
                reason=reason,
                stopped_tasks=stopped_tasks,
                detail=detail,
            ))

        logging.info("Successfully logged executer tracker termination.")


def get_signal_handler(termination_handler):

    def handler(signum, _):
        logging.info("Caught signal %s.", signal.Signals(signum).name)

        if gcloud.is_vm_preempted():
            reason = ExecuterTerminationReason.VM_PREEMPTED
        else:
            reason = ExecuterTerminationReason.INTERRUPTED

        termination_handler.log_termination(reason)

        sys.exit()

    return handler


def setup_cleanup_handlers(termination_handler):

    signal_handler = get_signal_handler(termination_handler)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
