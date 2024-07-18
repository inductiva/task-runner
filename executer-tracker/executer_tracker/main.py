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
import sys

from absl import app, logging

import executer_tracker
from executer_tracker import (
    apptainer_utils,
    cleanup,
    executers,
    redis_utils,
    task_execution_loop,
    utils,
)
from executer_tracker.register_executer import register_executer
from executer_tracker.task_request_handler import TaskRequestHandler
from executer_tracker.utils import config
from inductiva_api.task_status import ExecuterTerminationReason


def main(_):
    redis_hostname = os.getenv("REDIS_HOSTNAME")
    redis_port = os.getenv("REDIS_PORT", "6379")
    workdir = os.getenv("WORKDIR", "/workdir")
    executer_images_dir = os.getenv("EXECUTER_IMAGES_DIR", "/apptainer")
    if not executer_images_dir:
        logging.error("EXECUTER_IMAGES_DIR environment variable not set.")
        sys.exit(1)

    executer_images_remote_storage = os.getenv(
        "EXECUTER_IMAGES_REMOTE_STORAGE",
        None,
    )

    mpi_config = executers.MPIClusterConfiguration.from_env()

    logging.info("MPI configuration:")
    logging.info("  > hostfile: %s", mpi_config.hostfile_path)
    logging.info("  > share path: %s", mpi_config.share_path)
    logging.info("  > extra args: %s", mpi_config.extra_args)
    logging.info("  > num hosts: %d", mpi_config.num_hosts)

    max_timeout = None
    if config.gcloud.is_running_on_gcloud_vm():
        # Check if there are any metadata values that override the provided
        # environment variables.
        metadata_redis_hostname = config.gcloud.get_vm_metadata_value(
            "attributes/api-redis-hostname")
        if metadata_redis_hostname:
            redis_hostname = metadata_redis_hostname

        metadata_max_timeout = config.gcloud.get_vm_metadata_value(
            "attributes/idle_timeout")
        max_timeout = int(
            metadata_max_timeout) if metadata_max_timeout else None

    local_mode = os.getenv("LOCAL_MODE",
                           "true").lower() in ("true", "t", "yes", "y", 1)
    logging.info("Running in local mode: %s", local_mode)

    api_client = executer_tracker.ApiClient.from_env()

    machine_group_id = config.get_machine_group_id()
    if not machine_group_id:
        if not local_mode:
            raise ValueError("No machine group specified.")

        logging.info(
            "No machine group specified. Creating a new local machine group...")
        machine_group_id = api_client.create_local_machine_group()

    logging.info("Using machine group: %s", machine_group_id)

    redis_conn = redis_utils.create_redis_connection(redis_hostname, redis_port)

    executer_access_info = register_executer(
        api_client,
        machine_group_id=machine_group_id,
        mpi_cluster=mpi_config.is_cluster,
        num_mpi_hosts=mpi_config.num_hosts,
        local_mode=local_mode,
    )
    executer_uuid = executer_access_info.id

    redis_stream = executer_access_info.redis_stream
    redis_consumer_name = executer_access_info.redis_consumer_name
    redis_consumer_group = executer_access_info.redis_consumer_group

    apptainer_images_manager = apptainer_utils.ApptainerImagesManager(
        local_cache_dir=executer_images_dir,
        remote_storage_url=executer_images_remote_storage,
    )

    if local_mode:
        file_manager = executer_tracker.WebApiFileManager(
            api_client, executer_tracker_id=executer_uuid)
        task_fetcher = executer_tracker.WebApiTaskFetcher(
            api_client=api_client,
            executer_tracker_id=executer_uuid,
        )
        event_logger = executer_tracker.WebApiLogger(
            api_client=api_client,
            executer_tracker_id=executer_uuid,
        )
        message_listener = executer_tracker.WebApiTaskMessageListener(
            api_client=api_client,
            executer_tracker_id=executer_uuid,
        )
    else:
        artifact_store_root = os.getenv("ARTIFACT_STORE", "/mnt/artifacts")
        file_manager = executer_tracker.FsspecFileManager(artifact_store_root)
        task_fetcher = executer_tracker.RedisTaskFetcher(
            connection=redis_conn,
            stream=redis_stream,
            consumer_group=redis_consumer_group,
            consumer_name=redis_consumer_name,
        )
        event_logger = executer_tracker.RedisEventLogger(connection=redis_conn)
        message_listener = executer_tracker.RedisTaskMessageListener(
            connection=redis_conn)

    request_handler = TaskRequestHandler(
        executer_uuid=executer_uuid,
        workdir=workdir,
        mpi_config=mpi_config,
        apptainer_images_manager=apptainer_images_manager,
        api_client=api_client,
        event_logger=event_logger,
        message_listener=message_listener,
        file_manager=file_manager,
    )

    termination_handler = cleanup.TerminationHandler(
        executer_id=executer_uuid,
        local_mode=local_mode,
        redis_hostname=redis_hostname,
        redis_port=redis_port,
        request_handler=request_handler,
    )

    cleanup.setup_cleanup_handlers(termination_handler)

    monitoring_flag = True
    while monitoring_flag:
        try:
            task_execution_loop.start_loop(
                task_fetcher=task_fetcher,
                request_handler=request_handler,
                max_timeout=max_timeout,
            )
            monitoring_flag = False
        except TimeoutError:
            logging.info(
                "Max idle time reached. Terminating executer tracker...")
            status_code = api_client.kill_machine()

            if status_code == 422:
                logging.warn(
                    "Received 422 status code, cannot terminate due to minimum"
                    " VM constraint. Restarting monitoring process.")
                monitoring_flag = True
            else:
                reason = ExecuterTerminationReason.IDLE_TIMEOUT
                termination_handler.log_termination(reason)
                monitoring_flag = False
        except Exception as e:  # noqa: BLE001
            logging.exception("Caught exception: %s", str(e))
            logging.info("Terminating executer tracker...")
            reason = ExecuterTerminationReason.ERROR

            detail = utils.get_exception_root_cause_message(e)
            termination_handler.log_termination(reason, detail)

            monitoring_flag = False


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
