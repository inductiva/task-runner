"""Script that listens to a Redis stream and launches executer scripts.

TL;DR:

This is the entrypoint script that is launched in the executer Docker
container. It listens to a Redis stream in a blocking fashion: upon
receiving a request, it processes it with the correct executer script.
After processing the request, it tries to read from the Redis stream again,
only processing one request at a time.

The logic of processing a received request is defined in the `__call__` method
of the `TaskRequestHandler` class (task_request_handler.py file).

## Detailed description:

This script expects 5 environment variables to be set:
    EXECUTER_TYPE: type of executer that this executer_tracker will
        run. This is important in order to read from the correct
        stream, since we are using a different stream for each type
        of executer supported.
    REDIS_HOSTNAME: hostname of the Redis server to which to connect.
    REDIS_PORT: port in which the Redis server is accessible.
        Optional: uses 6379 by default.
    REDIS_CONSUMER_NAME: name that this executer tracker will use to
        read from the Redis stream. The name should be unique among all
        executers with the same EXECUTER_TYPE.
    ARTIFACT_STORE: path to shared directory, where artifacts can be accessed
        by both executers and the Web API.

In this file, a function named `monitor_redis_stream` is defined. The function
blocks until a request is received via the Redis stream. Then, the request
received in the Redis stream is passed as an argument to a callback function
that handles the received request. After the request is processed, the
`monitor_redis_stream` function acknowledges to the Redis stream that the
request has been processed (this is important so that we can get information
from the stream of how many requests are currently pending execution). Note
that this function only handles one request at a time, only trying to receive
a new request after the previous one is processed.

The logic of handling the request (the callback function mentioned above) is
defined in the `__call__` method of the TaskRequestHandler class, defined in
the task_request_handler.py file. As such, the `monitor_redis_stream` receives
as argument an object of the TaskRequestHandler class, and calls it when a
request is read from the Redis stream. Check the task_request_handler.py
file for more information on the logic of handling a received request.

The `monitor_redis_stream` function is wrapped in a try catch block, so that if
some exception (or ctrl+c) is caught and the script exits, the consumer name
is removed from the Redis stream. This is useful for monitoring the number of
currently active executer trackers.

Usage (note the required environment variables):
  python executer_tracker.py
"""
import atexit
import os
import signal
import sys

from absl import app, logging
from inductiva_api import events
from inductiva_api.events import RedisStreamEventLogger
from inductiva_api.task_status import ExecuterTerminationReason
from pyarrow import fs
from redis import Redis
from register_executer import register_executer
from task_request_handler import TaskRequestHandler
from utils import gcloud

DELIVER_NEW_MESSAGES = ">"


def create_redis_connection(redis_hostname, redis_port):
    redis_conn = Redis(
        redis_hostname,
        redis_port,
        retry_on_timeout=True,
        decode_responses=True,
    )

    return redis_conn


def monitor_redis_stream(redis_connection, stream_name: str,
                         consumer_group: str, consumer_name: str,
                         request_handler: TaskRequestHandler):
    """Monitors Redis stream, calling a callback to handle requests.

    The stream is read from via a consumer group. This requires that
    each executer reading from the stream has a name that is unique within
    the consumer group. Only one member of each consumer group receives
    a message, so this way only one executer handles each request.
    There's also an Ack response to notify the message as being
    successfully processed.

    Args:
        redis_connection: Connection to Redis server
        stream_name: Name of Redis Stream.
        consumer_group: Name of the consumer group.
        consumer_name: Name of the consumer: it should be
        request_handler: TaskRequestHandler instance that will handle
            the received request.
    """
    sleep_ms = 0  # 0ms means block forever

    logging.info("Starting monitoring of Redis stream \"%s\".", stream_name)
    while True:
        try:
            logging.info("Waiting for requests...")
            resp = redis_connection.xreadgroup(
                groupname=consumer_group,
                consumername=consumer_name,
                # Using the following ID will get messages that haven't
                # been delivered to any consumer.
                streams={stream_name: DELIVER_NEW_MESSAGES},
                count=1,  # reads one item at a time.
                block=sleep_ms,
            )
            if resp:
                _, messages = resp[0]
                stream_entry_id, request = messages[0]
                logging.info("REDIS ID: %s", str(stream_entry_id))
                logging.info("      --> %s", str(request))

                request_handler(request)

                # Acknowledge successful processing of the received message
                redis_connection.xack(stream_name, consumer_group,
                                      stream_entry_id)

        except ConnectionError as e:
            logging.info("ERROR REDIS CONNECTION: %s", str(e))


EVENTS_STREAM_NAME = "events"


def delete_redis_consumer(redis_hostname, redis_port, stream, consumer_group,
                          consumer_name):
    logging.info("`atexit` function: deleting \"%s\" from group \"%s\"...",
                 consumer_name, consumer_group)
    conn = create_redis_connection(redis_hostname, redis_port)
    conn.xgroup_delconsumer(stream, consumer_group, consumer_name)
    logging.info("`atexit` function executed successfully.")


def log_executer_termination(request_handler, redis_hostname, redis_port,
                             executer_uuid, reason):
    stopped_tasks = []
    if request_handler.is_simulation_running():
        logging.info("A simulation was being executed.")
        stopped_tasks.append(request_handler.current_task_id)

    redis_conn = create_redis_connection(redis_hostname, redis_port)
    event_logger = RedisStreamEventLogger(EVENTS_STREAM_NAME)

    event_logger.log_sync(
        redis_conn,
        events.ExecuterTerminated(
            uuid=executer_uuid,
            reason=reason,
            stopped_tasks=stopped_tasks,
        ))
    redis_conn.set(f"task:{request_handler.current_task_id}:status", "failed")

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
                           redis_stream, redis_consumer_name,
                           redis_consumer_group, request_handler):

    signal_handler = get_signal_handler(executer_uuid, redis_hostname,
                                        redis_port, request_handler)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGUSR1, signal_handler)

    atexit.register(
        delete_redis_consumer,
        redis_hostname,
        redis_port,
        redis_stream,
        redis_consumer_group,
        redis_consumer_name,
    )


def main(_):
    api_url = os.getenv("API_URL", "http://api.inductiva.ai")

    redis_hostname = os.getenv("REDIS_HOSTNAME")
    redis_port = os.getenv("REDIS_PORT", "6379")
    if not redis_hostname:
        raise ValueError("REDIS_HOSTNAME environment variable not set.")

    executer_type = os.getenv("EXECUTER_TYPE")
    if not executer_type:
        raise ValueError("EXECUTER_TYPE environment variable not set.")

    artifact_store_uri = os.getenv("ARTIFACT_STORE", "file:///mnt/artifacts")
    artifact_filesystem_root, base_path = fs.FileSystem.from_uri(
        artifact_store_uri)
    artifact_filesystem = fs.SubTreeFileSystem(base_path,
                                               artifact_filesystem_root)

    redis_conn = create_redis_connection(redis_hostname, redis_port)

    resource_pool_id = os.getenv("RESOURCE_POOL")
    if not resource_pool_id:
        logging.info("No resource pool specified. Using default.")
    else:
        logging.info("Using resource pool \"%s\".", resource_pool_id)
    executer_access_info = register_executer(
        api_url,
        executer_type,
        resource_pool_id=resource_pool_id,
    )
    executer_uuid = executer_access_info.id

    redis_stream = executer_access_info.redis_stream
    redis_consumer_name = executer_access_info.redis_consumer_name
    redis_consumer_group = executer_access_info.redis_consumer_group

    request_handler = TaskRequestHandler(
        redis_conn,
        artifact_filesystem,
        executer_uuid=executer_uuid,
    )

    setup_cleanup_handlers(executer_uuid, redis_hostname, redis_port,
                           redis_stream, redis_consumer_name,
                           redis_consumer_group, request_handler)

    try:
        monitor_redis_stream(
            redis_connection=redis_conn,
            stream_name=redis_stream,
            consumer_group=redis_consumer_group,
            consumer_name=redis_consumer_name,
            request_handler=request_handler,
        )
    except Exception as e:  # pylint: disable=broad-except
        logging.exception("Caught exception: %s", str(e))
        logging.info("Terminating executer tracker...")
        reason = ExecuterTerminationReason.ERROR
        log_executer_termination(request_handler, redis_hostname, redis_port,
                                 executer_uuid, reason)


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
