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
import os

from absl import app, logging
from pyarrow import fs
import docker

import redis_utils
import cleanup
from inductiva_api.task_status import ExecuterTerminationReason
from register_executer import register_executer
from task_request_handler import TaskRequestHandler
from utils import config


def main(_):
    api_url = os.getenv("API_URL", "http://web")
    redis_hostname = os.getenv("REDIS_HOSTNAME", "redis")
    redis_port = os.getenv("REDIS_PORT", "6379")
    artifact_store_uri = os.getenv("ARTIFACT_STORE", "/mnt/artifacts")

    shared_dir_host = os.getenv("SHARED_DIR_HOST")
    if not shared_dir_host:
        raise ValueError("SHARED_DIR_HOST environment variable not set.")

    shared_dir_local = os.getenv("SHARED_DIR_LOCAL")
    if not shared_dir_local:
        raise ValueError("SHARED_DIR_LOCAL environment variable not set.")

    artifact_filesystem_root, base_path = fs.FileSystem.from_uri(
        artifact_store_uri)
    artifact_filesystem_root = fs.SubTreeFileSystem(base_path,
                                                    artifact_filesystem_root)

    resource_pool_id = config.get_resource_pool_id()
    if not resource_pool_id:
        logging.info("No resource pool specified. Using default.")
    else:
        logging.info("Using resource pool: %s", resource_pool_id)

    redis_conn = redis_utils.create_redis_connection(redis_hostname, redis_port)
    docker_client = docker.from_env()

    executer_type_to_image = config.load_supported_executer_types(docker_client)

    executer_access_info = register_executer(
        api_url,
        list(executer_type_to_image.keys()),
        resource_pool_id=resource_pool_id,
    )
    executer_uuid = executer_access_info.id

    redis_streams = executer_access_info.redis_streams
    redis_consumer_name = executer_access_info.redis_consumer_name
    redis_consumer_group = executer_access_info.redis_consumer_group

    request_handler = TaskRequestHandler(
        redis_connection=redis_conn,
        docker_client=docker_client,
        docker_images=executer_type_to_image,
        artifact_filesystem=artifact_filesystem_root,
        executer_uuid=executer_uuid,
        shared_dir_host=shared_dir_host,
        shared_dir_local=shared_dir_local,
    )

    cleanup.setup_cleanup_handlers(executer_uuid, redis_hostname, redis_port,
                                   redis_streams, redis_consumer_name,
                                   redis_consumer_group, request_handler)

    try:
        redis_utils.monitor_redis_stream(
            redis_connection=redis_conn,
            stream_names=redis_streams,
            consumer_group=redis_consumer_group,
            consumer_name=redis_consumer_name,
            request_handler=request_handler,
        )
    except Exception as e:  # pylint: disable=broad-except
        logging.exception("Caught exception: %s", str(e))
        logging.info("Terminating executer tracker...")
        reason = ExecuterTerminationReason.ERROR
        detail = repr(e)
        cleanup.log_executer_termination(request_handler, redis_hostname,
                                         redis_port, executer_uuid, reason,
                                         detail)


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
