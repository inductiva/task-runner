"""Functions to perform cleanup when the executer tracker is terminated."""
import atexit
import signal
import sys
from absl import logging

import redis_utils
from inductiva_api import events
from inductiva_api.events import RedisStreamEventLoggerSync
from inductiva_api.task_status import ExecuterTerminationReason
from utils import gcloud


def log_executer_termination(request_handler,
                             redis_hostname,
                             redis_port,
                             executer_uuid,
                             reason,
                             detail=None):
    stopped_tasks = []
    if request_handler.is_task_running():
        logging.info("A task was being executed.")
        stopped_tasks.append(request_handler.task_id)

    redis_conn = redis_utils.create_redis_connection(redis_hostname, redis_port)
    event_logger = RedisStreamEventLoggerSync(redis_conn)

    event_logger.log(
        events.ExecuterTrackerTerminated(
            uuid=executer_uuid,
            reason=reason,
            stopped_tasks=stopped_tasks,
            detail=detail,
        ))

    logging.info("Successfully logged executer tracker termination.")


def get_signal_handler(executer_uuid, redis_hostname, redis_port,
                       request_handler):

    def handler(signum, _):
        logging.info("Caught signal %s.", signal.Signals(signum).name)

        if gcloud.is_vm_preempted():
            reason = ExecuterTerminationReason.VM_PREEMPTED
        else:
            reason = ExecuterTerminationReason.INTERRUPTED

        log_executer_termination(request_handler, redis_hostname, redis_port,
                                 executer_uuid, reason)
        sys.exit()

    return handler


def setup_cleanup_handlers(executer_uuid, redis_hostname, redis_port,
                           redis_streams, redis_consumer_name,
                           redis_consumer_group, request_handler):

    signal_handler = get_signal_handler(executer_uuid, redis_hostname,
                                        redis_port, request_handler)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    atexit.register(
        redis_utils.delete_redis_consumer_multiple_streams,
        redis_hostname,
        redis_port,
        redis_streams,
        redis_consumer_group,
        redis_consumer_name,
    )
