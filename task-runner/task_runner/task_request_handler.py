"""Handle execution of received task requests.

The TaskRequestHandler class implements the execution flow of a task, i.e.,
handles the logic related to setting up the working directory of an executer,
launching said executer, and providing the outputs to the Web API.
Note that, currently, request consumption is blocking.
"""
import copy
import datetime
import enum
import json
import os
import queue
import shutil
import threading
import time
import traceback
from typing import Optional
from uuid import UUID

from absl import logging
from task_runner import events
from task_runner.task_status import task_status

import task_runner
from task_runner import (
    ApiClient,
    SystemMonitor,
    api_methods_config,
    apptainer_utils,
    executers,
    observers,
    task_message_listener,
    utils,
)
from task_runner.operations_logger import OperationName, OperationsLogger
from task_runner.utils import files

KILL_MESSAGE = "kill"
INTERRUPT_MESSAGE = "interrupt"
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
    kill_task_thread_queue: queue.Queue,
    observer_manager: observers.ObserverManager,
) -> None:
    """Function to handle the kill request for the running task.

    This function is intended to be run in a separate thread. It waits for
    the "kill" message to be sent. When the message
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

        elif message == KILL_MESSAGE:
            kill_task_thread_queue.put(KILL_MESSAGE)

        # Must be a observer message
        else:
            try:
                observation_task = observers.Observer.parse_obj(
                    json.loads(message))
                observer_manager.start_observing(observation_task)
            except Exception:  # noqa: BLE001
                logging.error("Could not parse message: %s", message)


def interrupt_task_ttl_exceeded(
    executer: executers.BaseExecuter,
    ttl_exceeded_flag: threading.Event,
    ttl_function_started: threading.Event,
):
    """Interrupt the task when the time to live is exceeded."""
    ttl_function_started.set()
    logging.info("Time to live exceeded. Interrupting task...")
    was_terminated = executer.terminate()
    if was_terminated:
        ttl_exceeded_flag.set()
    logging.info("Task interrupted.")


def interrupt_task_on_kill_received(
    executer: executers.BaseExecuter,
    kill_thread_queue: queue.Queue,
    task_killed: threading.Event,
):
    """Interrupt the task when the kill command is received."""
    msg = kill_thread_queue.get()
    if msg == KILL_MESSAGE:
        logging.info("Received kill message. Killing task.")
        was_terminated = executer.terminate()
        if was_terminated:
            task_killed.set()
            logging.info("Task killed.")
    elif msg == INTERRUPT_MESSAGE:
        logging.info("Received interrupt message. Interrupting task.")
        executer.terminate()
    else:
        logging.info("Stopping kill command listener.")


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
        task_runner_uuid: UUID of the task_runner that handles the requests.
            Used for event logging purposes.
        workdir: Working directory.
        mpi_config: MPI configuration.
        apptainer_images_manager: ApptainerImagesManager instance. Used
            to download and cache Apptainer images locally.
        api_client: ApiClient instance. Used to communicate with the API.
        event_logger: Event logger.
        message_listener: Task message listener.
        file_manager: Filesystem manager.
    """

    def __init__(
        self,
        task_runner_uuid: UUID,
        workdir: str,
        mpi_config: executers.MPIClusterConfiguration,
        apptainer_images_manager: apptainer_utils.ApptainerImagesManager,
        api_client: ApiClient,
        event_logger: task_runner.BaseEventLogger,
        message_listener: task_message_listener.BaseTaskMessageListener,
        file_manager: task_runner.BaseFileManager,
        api_file_tracker: Optional[task_runner.ApiFileTracker] = None,
    ):
        self.task_runner_uuid = task_runner_uuid
        self.workdir = workdir
        self.mpi_config = mpi_config
        self.apptainer_images_manager = apptainer_images_manager
        self.api_client = api_client
        self.event_logger = event_logger
        self.message_listener = message_listener
        self.file_manager = file_manager
        self.api_file_tracker = api_file_tracker
        self.task_id = None
        self.task_workdir = None
        self.apptainer_image_path = None
        self.threads = []
        self.cleaning_up = False
        self._message_listener_thread = None
        self._kill_task_thread_queue = None
        self._shutting_down = False
        self._operations_logger = OperationsLogger(self.api_client)

        # If a share path for MPI is set, use it as the working directory.
        if self.mpi_config.share_path is not None:
            self.workdir = self.mpi_config.share_path

    def set_shutting_down(self):
        logging.info("Stopping task...")
        self._shutting_down = True

    def interrupt_task(self):
        if self._kill_task_thread_queue is None:
            raise RuntimeError("Failed to interrupt task.")

        self._kill_task_thread_queue.put(INTERRUPT_MESSAGE)

    def save_output(self, new_task_status=None, force=False):
        _ = self._pack_output()
        self._publish_event(events.TaskOutputUploaded(
            id=self.task_id,
            machine_id=self.task_runner_uuid,
            new_status=new_task_status),
                            force=force)
        return True

    def is_task_running(self) -> bool:
        """Checks if a task is currently running."""
        return self.task_id is not None and not self.cleaning_up

    def _publish_event(self, event: events.Event, force=False):
        if force or not self._shutting_down:
            self.event_logger.log(event)

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

    def _check_task_killed(self) -> bool:
        if self._kill_task_thread_queue is None:
            raise RuntimeError("Failed to check if task has been killed.")

        try:
            return self._kill_task_thread_queue.get(block=False) == KILL_MESSAGE
        except queue.Empty:
            return False

    def __call__(self, request: dict[str, str]) -> None:
        """Execute the task described by the request.

        Note that this method blocks until the task is completed or killed.
        While the task is being processed via the TaskTracker class, a thread
        is set to poll the API, in which a "kill" message may be
        received. If the message is received, then the subprocess running the
        requested task is killed.

        Args:
            request: Request describing the task to be executed.
        """
        self.task_id = request["id"]
        self.project_id = request["project_id"]
        self.task_dir_remote = request["task_dir"]
        self.submitted_timestamp = request.get("submitted_timestamp")
        self.input_resources = json.loads(request.get("input_resources", "[]"))
        # convert to bool because stream_zip is either 't' or 'f'
        self.stream_zip = True if request.get("stream_zip",
                                              "t") == "t" else False
        self.compress_with = request.get("compress_with", "AUTO")
        self.cleaning_up = False
        self._kill_task_thread_queue = queue.Queue()

        self.observer_manager = observers.ObserverManager(
            self.event_logger, check_interval_seconds=5)

        self._log_task_picked_up()
        safely_delete = False

        try:
            self._message_listener_thread = threading.Thread(
                target=task_message_listener_loop,
                args=(
                    self.message_listener,
                    self.task_id,
                    self._kill_task_thread_queue,
                    self.observer_manager,
                ),
                daemon=True,
            )
            self._message_listener_thread.start()

            image_uri = request["container_image"]

            operation = self._operations_logger.start_operation(
                OperationName.DOWNLOAD_CONTAINER,
                self.task_id,
                attributes={
                    "image_uri": image_uri,
                },
            )

            image_path, download_time, container_source, image_size = (
                self.apptainer_images_manager.get(image_uri, self.workdir))

            operation.end(attributes={
                "execution_time_s": download_time,
                "source": container_source.value,
                "size_bytes": image_size,
            },)

            self.apptainer_image_path = image_path

            if download_time is not None:
                self._post_task_metric(utils.DOWNLOAD_EXECUTER_IMAGE,
                                       download_time)

                self._post_task_metric(utils.EXECUTER_IMAGE_SIZE, image_size)

            if self._check_task_killed():
                self._publish_event(
                    events.TaskKilled(
                        id=self.task_id,
                        machine_id=self.task_runner_uuid,
                    ))
                return

            self.task_workdir = self._setup_working_dir(self.task_dir_remote)

            # Note: ideally we would pass the sim_dir to the observer manager
            # however commands run in path /workdir/<task_id>/output/artifacts
            self._observer_manager_thread = threading.Thread(
                target=self.observer_manager.run,
                args=(
                    os.path.join("/workdir", self.task_id, "output/artifacts"),
                    self.task_id,
                ),
                daemon=True,
            )
            self._observer_manager_thread.start()

            if self._check_task_killed():
                self._publish_event(
                    events.TaskKilled(
                        id=self.task_id,
                        machine_id=self.task_runner_uuid,
                    ))
                return

            computation_start_time = utils.now_utc()
            self._publish_event(
                events.TaskWorkStarted(
                    timestamp=computation_start_time,
                    id=self.task_id,
                    machine_id=self.task_runner_uuid,
                ))

            exit_code, exit_reason = self._execute_request(request)
            logging.info("Task exit reason: %s", exit_reason)

            computation_end_time = utils.now_utc()
            self._publish_event(
                events.TaskWorkFinished(
                    timestamp=computation_end_time,
                    id=self.task_id,
                    machine_id=self.task_runner_uuid,
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

            if exit_reason == TaskExitReason.KILLED:
                new_status = task_status.TaskStatusCode.KILLED.value
            elif exit_reason == TaskExitReason.TTL_EXCEEDED:
                new_status = task_status.TaskStatusCode.TTL_EXCEEDED.value
            else:
                new_status = (task_status.TaskStatusCode.SUCCESS.value
                              if exit_code == 0 else
                              task_status.TaskStatusCode.FAILED.value)

            safely_delete = self.save_output(new_task_status=new_status)

            self.message_listener.unblock(self.task_id)
            if self._message_listener_thread:
                self._message_listener_thread.join()
                logging.info("Message listener thread stopped.")

            self.observer_manager.stop()
            self._observer_manager_thread.join()
            logging.info("Observer manager thread stopped.")

        # Catch all exceptions to ensure that we log the error message
        except Exception as e:  # noqa: BLE001
            message = utils.get_exception_root_cause_message(e)
            try:
                self._publish_event(
                    events.TaskExecutionFailed(
                        id=self.task_id,
                        machine_id=self.task_runner_uuid,
                        error_message=message,
                        traceback=traceback.format_exc(),
                    ))

                safely_delete = self.save_output()

            except Exception as e:  # noqa: BLE001
                logging.exception("Failed to save output: %s", e)
                message = utils.get_exception_root_cause_message(e)
                self._publish_event(
                    events.TaskOutputUploadFailed(
                        id=self.task_id,
                        machine_id=self.task_runner_uuid,
                        error_message=message,
                        traceback=traceback.format_exc(),
                    ))
                safely_delete = False

        finally:
            self.cleaning_up = True
            self._cleanup(safely_delete)

    def _setup_working_dir(self, task_dir_remote) -> str:
        """Setup the working directory for the task.

        Returns:
            Path to the working directory for the currently
            running task.
        """
        assert self.task_id is not None, (
            "'_setup_working_dir' called without a task ID.")

        task_workdir = os.path.join(self.workdir, self.task_id)
        sim_workdir = os.path.join(task_workdir, "sim_dir")

        if os.path.exists(task_workdir):
            logging.info("Working directory already existed: %s", task_workdir)
            logging.info("Removing directory: %s", task_workdir)
            shutil.rmtree(task_workdir)

        os.makedirs(task_workdir)
        os.makedirs(sim_workdir)

        # Download input resources first so they can be overwriten
        # by the task files
        if self.input_resources:
            download_duration = self.file_manager.download_input_resources(
                self.input_resources, sim_workdir, self.workdir)

        tmp_zip_path = os.path.join(self.workdir, "file.zip")

        operation = self._operations_logger.start_operation(
            OperationName.DOWNLOAD_INPUT,
            self.task_id,
        )
        download_duration = self.file_manager.download_input(
            self.task_id,
            task_dir_remote,
            tmp_zip_path,
        )
        operation.end(attributes={"execution_time_s": download_duration})
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

        operation = self._operations_logger.start_operation(
            OperationName.UNCOMPRESS_INPUT,
            self.task_id,
        )
        unzip_duration = files.extract_zip_archive(
            zip_path=tmp_zip_path,
            dest_dir=task_workdir,
        )

        os.remove(tmp_zip_path)
        operation.end(attributes={"execution_time_s": unzip_duration})

        if self.api_file_tracker:
            self.api_file_tracker.start(self.task_id)

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
    ) -> tuple[int, TaskExitReason]:
        """Execute the request.

        This uses a second thread to listen for possible "kill" messages from
        the API.

        Returns:
            tuple of the exit code of the task and a bool representing if the
            task was killed.
        """
        assert self.task_id is not None, (
            "'_execute_request' called without a task ID.")

        executer = self._build_executer(request)

        task_killed_flag = threading.Event()

        kill_task_thread = threading.Thread(
            target=interrupt_task_on_kill_received,
            args=(
                executer,
                self._kill_task_thread_queue,
                task_killed_flag,
            ),
            daemon=True,
        )
        kill_task_thread.start()

        ttl_exceeded_flag = threading.Event()
        ttl_function_started = threading.Event()
        ttl_str = request.get("time_to_live_seconds")
        ttl_timer = None
        if ttl_str:
            ttl = float(ttl_str)
            logging.info("Time to live: %s seconds", ttl)
            ttl_timer = threading.Timer(
                ttl,
                interrupt_task_ttl_exceeded,
                args=(executer, ttl_exceeded_flag, ttl_function_started),
            )
            ttl_timer.daemon = True
            ttl_timer.start()

        exit_code = executer.run()
        logging.info("Executer finished running.")

        self._kill_task_thread_queue.put(TASK_DONE_MESSAGE)
        kill_task_thread.join()
        logging.info("Kill command listener thread stopped.")

        if ttl_timer:
            # If the TTL timer was still counting down, cancel it
            if not ttl_function_started.is_set():
                ttl_timer.cancel()

            logging.info("Waiting for TTL timer thread to finish...")
            ttl_timer.finished.wait()
            logging.info("TTL timer thread stopped.")

        exit_reason = TaskExitReason.NORMAL
        if task_killed_flag.is_set():
            exit_reason = TaskExitReason.KILLED
        elif ttl_exceeded_flag.is_set():
            exit_reason = TaskExitReason.TTL_EXCEEDED

        return exit_code, exit_reason

    def _pack_output(self) -> int:
        """Compress outputs and store them in the shared drive."""
        if self.task_workdir is None:
            logging.error("Working directory not found.")
            return

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

        output_zipped_bytes, zip_duration, upload_duration = \
            self.file_manager.upload_output(
                self.task_id,
                self.task_dir_remote,
                output_dir,
                stream_zip=self.stream_zip,
                compress_with=self.compress_with,
                operations_logger=self._operations_logger,
                event_logger=self.event_logger,
                task_runner_uuid=self.task_runner_uuid,
            )

        logging.info("Output zipped in: %s seconds", zip_duration)

        if zip_duration:
            self._post_task_metric(
                utils.OUTPUT_COMPRESSION_SECONDS,
                zip_duration,
            )

        logging.info("Output zipped size: %s bytes", output_zipped_bytes)

        self._post_task_metric(
            utils.OUTPUT_ZIPPED_SIZE,
            output_zipped_bytes,
        )

        output_zip_path_remote = os.path.join(
            self.task_dir_remote,
            utils.OUTPUT_ZIP_FILENAME,
        )

        logging.info(
            "Uploaded output zip to: %s, in %s seconds",
            output_zip_path_remote,
            upload_duration,
        )

        self._post_task_metric(utils.UPLOAD_OUTPUT, upload_duration)

        return output_zipped_bytes

    def _cleanup(self, rm_dir):
        """Cleanup after task execution.

        Deletes the working directory of the task.
        Waits for all threads to finish.

        Args:
            working_dir_local: Working directory of the executer that performed
                the task.
        """
        if rm_dir and self.task_workdir is not None:
            logging.info("Cleaning up working directory: %s", self.task_workdir)
            shutil.rmtree(self.task_workdir, ignore_errors=True)
        self.task_workdir = None
        if self.api_file_tracker:
            self.api_file_tracker.stop(self.task_id)
        self._message_listener_thread = None

        for thread in self.threads:
            thread.join()

        self.task_id = None

    def _build_executer(self, request) -> executers.BaseExecuter:
        """Build Python command to run a requested task.

        NOTE: this method is a candidate for improvement.

        Args:
            request: Request for which to build a command.

        Returns:
            Python command to execute received request.
        """
        simulator = request["simulator"]
        container_image = request["container_image"]

        executer_class = api_methods_config.get_executer(simulator)
        if executer_class is None:
            raise ValueError(f"Executer not found for simulator: {simulator}")

        extra_params = json.loads(request.get("extra_params", {}))

        return executer_class(
            working_dir=self.task_workdir,
            container_image=self.apptainer_image_path,
            mpi_config=copy.deepcopy(self.mpi_config),
            exec_command_logger=executers.ExecCommandLogger(
                self.task_id,
                self._operations_logger,
            ),
            system_monitor=SystemMonitor(
                task_id=self.task_id,
                task_runner_uuid=self.task_runner_uuid,
                event_logger=self.event_logger,
                output_stalled_threshold_minutes=None
                if "openfast" in container_image else 30,
            ),
            extra_params=extra_params,
        )
