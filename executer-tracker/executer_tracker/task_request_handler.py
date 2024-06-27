"""Handle execution of received task requests.

The TaskRequestHandler class implements the execution flow of a task, i.e.,
handles the logic related to setting up the working directory of an executer,
launching said executer, and providing the outputs to the Web API.
Note that, currently, request consumption is blocking.
"""
import copy
import datetime
import enum
import os
import shutil
import tempfile
import threading
import time
from typing import Dict, Tuple
from uuid import UUID

from absl import logging

import executer_tracker
from executer_tracker import (
    ApiClient,
    api_methods_config,
    apptainer_utils,
    executers,
    task_message_listener,
    utils,
)
from executer_tracker.utils import files, loki
from inductiva_api import events
from inductiva_api.task_status import task_status

KILL_MESSAGE = "kill"
ENABLE_LOGGING_STREAM_MESSAGE = "enable_logging_stream"
DISABLE_LOGGING_STREAM_MESSAGE = "disable_logging_stream"
TASK_DONE_MESSAGE = "done"


class TaskExitReason(enum.Enum):
    NORMAL = "normal"
    KILLED = "killed"
    TTL_EXCEEDED = "ttl-exceeded"


def task_message_listener_loop(
    listener: task_message_listener.BaseTaskMessageListener,
    task_id: str,
    executer: executers.BaseExecuter,
    killed_flag: threading.Event,
) -> None:
    """Function to handle the kill request for the running task.

    This function is intended to be run in a separate thread. It waits for
    the "kill" message to be sent to the task's Redis queue. When the message
    is received, the task is killed.

    Args:
        task_id: ID of the running task.
        killed_flag: Flag to signal that the task was killed.
    """
    while True:

        logging.info("Waiting for task related messages ...")
        message = listener.receive(task_id)
        logging.info("Received message: %s", message)

        if message == TASK_DONE_MESSAGE:
            return

        if message == KILL_MESSAGE:
            logging.info("Received kill message. Killing task.")
            executer.terminate()
            logging.info("Task killed.")

            # set flag so that the main thread knows the task was killed
            killed_flag.set()
            return

        elif message == ENABLE_LOGGING_STREAM_MESSAGE:
            executer.loki_logger.enable()
            logging.info("Logging stream enabled.")

        elif message == DISABLE_LOGGING_STREAM_MESSAGE:
            executer.loki_logger.disable()
            logging.info("Logging stream disabled.")


def interrupt_task_ttl_exceeded(
    executer: executers.BaseExecuter,
    ttl_exceeded_flag: threading.Event,
):
    """Interrupt the task when the time to live is exceeded."""
    logging.info("Time to live exceeded. Interrupting task...")
    executer.terminate()
    ttl_exceeded_flag.set()
    logging.info("Task interrupted.")


class TaskRequestHandler:
    """Task request processing logic and task execution flow.

    The TaskRequestHandler implements the execution flow of a task. Its
    intended usage is within a loop where requests are listened for.
    After a request arrives, it is passed to an instance of TaskRequestHandler
    for blocking execution of the request. The TaskRequestHandler defines
    the __call__ method, so passing a request to an instance of
    TaskRequestHandler is a call like `request_handler(request)`, where
    `request_handler` is the TaskRequestHandler instance and `request` is
    the request for consumption.

    Attributes:
        redis_connection: Redis connection handler.
        filesystem: fsspec filesystem handler.
        artifact_store_root: Root directory for storing artifacts.
        executer_uuid: UUID of the executer that handles the requests.
            Used for event logging purposes.
        workdir: Working directory.
        mpi_config: MPI configuration.
        apptainer_images_manager: ApptainerImagesManager instance. Used
            to download and cache Apptainer images locally.
        api_client: ApiClient instance. Used to communicate with the API.
    """

    def __init__(
        self,
        executer_uuid: UUID,
        workdir: str,
        mpi_config: executers.MPIConfiguration,
        apptainer_images_manager: apptainer_utils.ApptainerImagesManager,
        api_client: ApiClient,
        event_logger: executer_tracker.BaseEventLogger,
        message_listener: task_message_listener.BaseTaskMessageListener,
        file_manager: executer_tracker.BaseFileManager,
    ):
        self.executer_uuid = executer_uuid
        self.workdir = workdir
        self.mpi_config = mpi_config
        self.apptainer_images_manager = apptainer_images_manager
        self.api_client = api_client
        self.event_logger = event_logger
        self.message_listener = message_listener
        self.file_manager = file_manager
        self.task_id = None
        self.loki_logger = None
        self.task_workdir = None
        self.apptainer_image_path = None
        self.threads = []

        # If a share path for MPI is set, use it as the working directory.
        if self.mpi_config.share_path is not None:
            self.workdir = self.mpi_config.share_path

    def is_task_running(self) -> bool:
        """Checks if a task is currently running."""
        return self.task_id is not None

    def _post_task_metric(self, metric: str, value: float):
        """Post a metric for the currently running task.

        The post request is done in a separate thread to allow retries
        without blocking the task execution.
        When the first metric (donwload input) is posted, the DB updater
        may not have updated the task status yet. In this case the task won't
        be assigned to the machine and the request will be rejected.
        """
        thread = threading.Thread(
            target=self.api_client.post_task_metric,
            args=(self.task_id, metric, value),
            daemon=True,
        )
        thread.start()
        self.threads.append(thread)

    def _log_task_picked_up(self):
        """Log that a task was picked up by the executer."""
        assert self.task_id is not None
        picked_up_timestamp = utils.now_utc()

        if self.submitted_timestamp is not None:
            submitted_timestamp = datetime.datetime.fromisoformat(
                self.submitted_timestamp)
            logging.info("Task submitted at: %s", self.submitted_timestamp)
            while picked_up_timestamp <= submitted_timestamp:
                time.sleep(0.01)
                picked_up_timestamp = utils.now_utc()

            queue_time = (picked_up_timestamp -
                          submitted_timestamp).total_seconds()
            self._post_task_metric(utils.QUEUE_TIME_SECONDS, queue_time)

        logging.info("Task picked up at: %s", picked_up_timestamp)

        self.event_logger.log(
            events.TaskPickedUp(
                timestamp=picked_up_timestamp,
                id=self.task_id,
                machine_id=self.executer_uuid,
            ))

    def __call__(self, request: Dict[str, str]) -> None:
        """Execute the task described by the request.

        Note that this method blocks until the task is completed or killed.
        While the task is being processed via the TaskTracker class, a thread
        is set to listen to a Redis queue, in which a "kill" message may be
        received. If the message is received, then the subprocess running the
        requested task is killed.

        Args:
            request: Request describing the task to be executed.
        """
        self.task_id = request["id"]
        self.project_id = request["project_id"]
        self.task_dir_remote = request["task_dir"]
        self.submitted_timestamp = request.get("submitted_timestamp")
        self.loki_logger = loki.LokiLogger(
            task_id=self.task_id,
            project_id=self.project_id,
        )

        self._log_task_picked_up()

        try:
            image_path, download_time = self.apptainer_images_manager.get(
                request["container_image"])
            self.apptainer_image_path = image_path

            if download_time is not None:
                self._post_task_metric(utils.DOWNLOAD_EXECUTER_IMAGE,
                                       download_time)

            self.task_workdir = self._setup_working_dir(self.task_dir_remote)

            computation_start_time = utils.now_utc()
            self.event_logger.log(
                events.TaskWorkStarted(
                    timestamp=computation_start_time,
                    id=self.task_id,
                    machine_id=self.executer_uuid,
                ))
            exit_code, exit_reason = self._execute_request(request)
            logging.info("Task exit reason: %s", exit_reason)

            computation_end_time = utils.now_utc()
            self.event_logger.log(
                events.TaskWorkFinished(
                    timestamp=computation_end_time,
                    id=self.task_id,
                    machine_id=self.executer_uuid,
                ))

            computation_seconds = (computation_end_time -
                                   computation_start_time).total_seconds()
            logging.info(
                "Task computation time: %s seconds",
                computation_seconds,
            )

            self._post_task_metric(
                utils.COMPUTATION_SECONDS,
                computation_seconds,
            )

            output_size = self._pack_output()

            if exit_reason == TaskExitReason.KILLED:
                new_status = task_status.TaskStatusCode.KILLED.value
            elif exit_reason == TaskExitReason.TTL_EXCEEDED:
                new_status = task_status.TaskStatusCode.TTL_EXCEEDED.value
            else:
                new_status = (task_status.TaskStatusCode.SUCCESS.value
                              if exit_code == 0 else
                              task_status.TaskStatusCode.FAILED.value)

            self.event_logger.log(
                events.TaskOutputUploaded(
                    id=self.task_id,
                    machine_id=self.executer_uuid,
                    new_status=new_status,
                    output_size=output_size,
                ))

        # Catch all exceptions to ensure that we log the error message
        except Exception as e:  # noqa: BLE001
            message = utils.get_exception_root_cause_message(e)
            self.event_logger.log(
                events.TaskExecutionFailed(
                    id=self.task_id,
                    machine_id=self.executer_uuid,
                    error_message=message,
                ))

        finally:
            self._cleanup()
            self.task_id = None

    def _setup_working_dir(self, task_dir_remote) -> str:
        """Setup the working directory for the task.

        Returns:
            Path to the working directory for the currently
            running task.
        """
        assert self.task_id is not None, (
            "'_setup_working_dir' called without a task ID.")

        task_workdir = os.path.join(self.workdir, self.task_id)

        if os.path.exists(task_workdir):
            logging.info("Working directory already existed: %s", task_workdir)
            logging.info("Removing directory: %s", task_workdir)
            shutil.rmtree(task_workdir)

        os.makedirs(task_workdir)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_zip_path = os.path.join(tmp_dir, "file.zip")

            download_duration = self.file_manager.download_input(
                self.task_id,
                task_dir_remote,
                tmp_zip_path,
            )

            logging.info(
                "Downloaded zip to: %s, in %s seconds.",
                tmp_zip_path,
                download_duration,
            )

            self._post_task_metric(utils.DOWNLOAD_INPUT, download_duration)

            input_zipped_size_bytes = os.path.getsize(tmp_zip_path)
            logging.info("Input zipped size: %s bytes", input_zipped_size_bytes)

            self._post_task_metric(
                utils.INPUT_ZIPPED_SIZE,
                input_zipped_size_bytes,
            )

            unzip_duration = files.extract_zip_archive(
                zip_path=tmp_zip_path,
                dest_dir=task_workdir,
            )

            logging.info(
                "Extracted zip to: %s, in %s seconds",
                task_workdir,
                unzip_duration,
            )

            self._post_task_metric(utils.UNZIP_INPUT, unzip_duration)

            input_size_bytes = files.get_dir_size(task_workdir)
            logging.info("Input size: %s bytes", input_size_bytes)

            if input_size_bytes is not None:
                self._post_task_metric(utils.INPUT_SIZE, input_size_bytes)

        return task_workdir

    def _execute_request(
        self,
        request,
    ) -> Tuple[int, TaskExitReason]:
        """Execute the request.

        This uses a second thread to listen for possible "kill" messages from
        the API.

        Returns:
            Tuple of the exit code of the task and a bool representing if the
            task was killed.
        """
        assert self.task_id is not None, (
            "'_execute_request' called without a task ID.")

        executer = self._build_executer(request)

        task_killed_flag = threading.Event()
        thread = threading.Thread(
            target=task_message_listener_loop,
            args=(
                self.message_listener,
                self.task_id,
                executer,
                task_killed_flag,
            ),
            daemon=True,
        )
        thread.start()

        ttl_exceeded_flag = threading.Event()
        ttl_str = request.get("time_to_live_seconds")
        ttl_timer = None
        if ttl_str:
            ttl = float(ttl_str)
            logging.info("Time to live: %s seconds", ttl)
            ttl_timer = threading.Timer(
                ttl,
                interrupt_task_ttl_exceeded,
                args=(executer, ttl_exceeded_flag),
            )
            ttl_timer.start()

        exit_code = executer.run()

        if ttl_timer and not ttl_exceeded_flag.is_set():
            ttl_timer.cancel()

        logging.info("Executer finished running.")
        self.message_listener.unblock(self.task_id)

        thread.join()
        logging.info("Message listener thread stopped.")

        exit_reason = TaskExitReason.NORMAL
        if task_killed_flag.is_set():
            exit_reason = TaskExitReason.KILLED
        elif ttl_exceeded_flag.is_set():
            exit_reason = TaskExitReason.TTL_EXCEEDED

        return exit_code, exit_reason

    def _pack_output(self) -> int:
        """Compress outputs and store them in the shared drive."""
        output_zipped_size_bytes = None

        output_dir = os.path.join(self.task_workdir, utils.OUTPUT_DIR)
        if not os.path.exists(output_dir):
            logging.error("Output directory not found: %s", output_dir)
            return

        output_size_bytes = files.get_dir_size(output_dir)
        logging.info("Output size: %s bytes", output_size_bytes)

        if output_size_bytes is not None:
            self._post_task_metric(utils.OUTPUT_SIZE, output_size_bytes)

        output_total_files = files.get_dir_total_files(output_dir)
        logging.info("Output total files: %s", output_total_files)

        if output_total_files is not None:
            self._post_task_metric(utils.OUTPUT_TOTAL_FILES, output_total_files)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_zip_path_local = os.path.join(
                tmp_dir,
                utils.OUTPUT_ZIP_FILENAME,
            )

            zip_duration = files.make_zip_archive(
                output_zip_path_local,
                output_dir,
            )

            logging.info(
                "Created output zip archive: %s, in %s seconds",
                output_zip_path_local,
                zip_duration,
            )

            self._post_task_metric(utils.ZIP_OUTPUT, zip_duration)

            output_zipped_size_bytes = os.path.getsize(output_zip_path_local)
            logging.info("Output zipped size: %s bytes",
                         output_zipped_size_bytes)

            self._post_task_metric(
                utils.OUTPUT_ZIPPED_SIZE,
                output_zipped_size_bytes,
            )

            output_zip_path_remote = os.path.join(
                self.task_dir_remote,
                utils.OUTPUT_ZIP_FILENAME,
            )

            upload_duration = self.file_manager.upload_output(
                self.task_id,
                self.task_dir_remote,
                output_zip_path_local,
            )

            logging.info(
                "Uploaded output zip to: %s, in %s seconds",
                output_zip_path_remote,
                upload_duration,
            )

            self._post_task_metric(utils.UPLOAD_OUTPUT, upload_duration)

        return output_zipped_size_bytes

    def _cleanup(self):
        """Cleanup after task execution.

        Deletes the working directory of the task.
        Waits for all threads to finish.

        Args:
            working_dir_local: Working directory of the executer that performed
                the task.
        """
        if self.task_workdir is not None:
            logging.info("Cleaning up working directory: %s", self.task_workdir)
            shutil.rmtree(self.task_workdir, ignore_errors=True)
        self.task_workdir = None

        for thread in self.threads:
            thread.join()

    def _build_executer(self, request) -> executers.BaseExecuter:
        """Build Python command to run a requested task.

        NOTE: this method is a candidate for improvement.

        Args:
            request: Request for which to build a command.

        Returns:
            Python command to execute received request.
        """
        method = request["method"]

        executer_class = api_methods_config.api_method_to_script[method]

        return executer_class(
            self.task_workdir,
            self.apptainer_image_path,
            copy.deepcopy(self.mpi_config),
            self.loki_logger,
        )
