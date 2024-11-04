"""Script that requests simulations from the API and launches executer scripts.

This is the entrypoint script that is launched in the executer Docker
container. It requests a simulation from the API: upon
receiving a request, it processes it with the correct executer script.
After processing the request, it requests from the API again,
only processing one request at a time.

The logic of processing a received request is defined in the `__call__` method
of the `TaskRequestHandler` class (task_request_handler.py file).

Usage (note the required environment variables):
  python main.py
"""
import json
import os
import sys
import uuid

from absl import app, logging
from inductiva_api.task_status import ExecuterTerminationReason

import task_runner
from task_runner import (
    apptainer_utils,
    cleanup,
    executers,
    task_execution_loop,
    utils,
)
from task_runner.register_executer import register_executer
from task_runner.task_request_handler import TaskRequestHandler


def _log_task_runner_id(path, task_runner_id: uuid.UUID):
    if not path:
        return

    with open(path, "w", encoding="UTF-8") as f:
        json.dump({"id": str(task_runner_id)}, f)


def main(_):
    workdir = os.getenv("WORKDIR", "/workdir")
    executer_images_dir = os.getenv("EXECUTER_IMAGES_DIR", "/apptainer")
    if not executer_images_dir:
        logging.error("EXECUTER_IMAGES_DIR environment variable not set.")
        sys.exit(1)

    executer_images_remote_storage = os.getenv(
        "EXECUTER_IMAGES_REMOTE_STORAGE",
        None,
    )

    task_runner_id_path = os.getenv("TASK_RUNNER_ID_PATH")

    mpi_config = executers.MPIClusterConfiguration.from_env()

    logging.info("MPI configuration:")
    logging.info("  > hostfile: %s", mpi_config.hostfile_path)
    logging.info("  > share path: %s", mpi_config.share_path)
    logging.info("  > extra args: %s", mpi_config.extra_args)
    logging.info("  > num hosts: %d", mpi_config.num_hosts)
    logging.info("  > default version: %s", mpi_config.default_version)
    logging.info("  > available versions: %s",
                 ", ".join(mpi_config.list_available_versions()))

    max_idle_timeout = None

    max_idle_timeout = os.getenv("MAX_IDLE_TIMEOUT")
    max_idle_timeout = int(max_idle_timeout) if max_idle_timeout else None

    api_client = task_runner.ApiClient.from_env()

    machine_group_info = task_runner.MachineGroupInfo.from_api(api_client)

    machine_group_id = machine_group_info.id
    local_mode = machine_group_info.local_mode

    if local_mode:
        api_client.start_local_machine_group(machine_group_id)

    logging.info("Using machine group: %s", machine_group_id)

    executer_access_info = register_executer(
        api_client,
        machine_group_id=machine_group_id,
        mpi_cluster=mpi_config.is_cluster,
        num_mpi_hosts=mpi_config.num_hosts,
        local_mode=local_mode,
    )
    executer_uuid = executer_access_info.id
    _log_task_runner_id(task_runner_id_path, executer_uuid)

    apptainer_images_manager = apptainer_utils.ApptainerImagesManager(
        local_cache_dir=executer_images_dir,
        remote_storage_url=executer_images_remote_storage,
    )

    file_manager = task_runner.WebApiFileManager(api_client,
                                                 task_runner_id=executer_uuid)
    task_fetcher = task_runner.WebApiTaskFetcher(
        api_client=api_client,
        task_runner_id=executer_uuid,
    )
    event_logger = task_runner.WebApiLogger(
        api_client=api_client,
        task_runner_id=executer_uuid,
    )
    message_listener = task_runner.WebApiTaskMessageListener(
        api_client=api_client,
        task_runner_id=executer_uuid,
    )

    api_file_tracker = task_runner.ApiFileTracker() if local_mode else None

    request_handler = TaskRequestHandler(
        executer_uuid=executer_uuid,
        workdir=workdir,
        mpi_config=mpi_config,
        apptainer_images_manager=apptainer_images_manager,
        api_client=api_client,
        event_logger=event_logger,
        message_listener=message_listener,
        file_manager=file_manager,
        api_file_tracker=api_file_tracker,
    )

    termination_handler = cleanup.TerminationHandler(
        executer_id=executer_uuid,
        request_handler=request_handler,
    )

    cleanup.setup_cleanup_handlers(termination_handler)

    monitoring_flag = True
    while monitoring_flag:
        try:
            task_execution_loop.start_loop(
                task_fetcher=task_fetcher,
                request_handler=request_handler,
                max_idle_timeout=max_idle_timeout,
            )
            monitoring_flag = False
        except cleanup.ScaleDownTimeoutError as e:
            logging.exception("Caught exception: %s", str(e))
            logging.info("Terminating task runner...")
            status_code = api_client.kill_machine()

            if status_code == 422:
                logging.warn(
                    "Received 422 status code, cannot terminate due to minimum"
                    " VM constraint. Restarting monitoring process.")
                monitoring_flag = True
            else:
                termination_handler.log_termination(e.reason, e.detail)
                monitoring_flag = False
        except cleanup.ExecuterTerminationError as e:
            logging.exception("Caught exception: %s", str(e))
            logging.info("Terminating task runner...")
            termination_handler.log_termination(e.reason, e.detail)
            monitoring_flag = False
        except Exception as e:  # noqa: BLE001
            logging.exception("Caught exception: %s", str(e))
            logging.info("Terminating task runner...")
            reason = ExecuterTerminationReason.ERROR

            detail = utils.get_exception_root_cause_message(e)
            termination_handler.log_termination(reason,
                                                detail,
                                                save_traceback=True)

            monitoring_flag = False


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
