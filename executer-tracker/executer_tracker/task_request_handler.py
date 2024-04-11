"""Handle execution of received task requests.

The TaskRequestHandler class implements the execution flow of a task, i.e.,
handles the logic related to setting up the working directory of an executer,
launching said executer, and providing the outputs to the Web API.
Note that, currently, request consumption is blocking.
"""
import copy
import os
import shutil
import tempfile
import threading
from typing import Dict, Tuple
from uuid import UUID

import api_methods_config
import fsspec
import redis
import utils
from absl import logging
from utils import config, files, loki, make_task_key

from executer_tracker import executers
from inductiva_api import events
from inductiva_api.events import RedisStreamEventLoggerSync
from inductiva_api.task_status import task_status

TASK_COMMANDS_QUEUE = "commands"
KILL_MESSAGE = "kill"
ENABLE_LOGGING_STREAM_MESSAGE = "enable_logging_stream"
DISABLE_LOGGING_STREAM_MESSAGE = "disable_logging_stream"


def redis_command_msg_catcher(
    redis_conn: redis.Redis,
    task_id: str,
    executer: executers.BaseExecuter,
    killed_flag: threading.Event,
) -> None:
    """Function to handle the kill request for the running task.

    This function is intended to be run in a separate thread. It waits for
    the "kill" message to be sent to the task's Redis queue. When the message
    is received, the task is killed.

    Args:
        redis_conn: Redis connection.
        task_id: ID of the running task.
        task_tracker: TaskTracker instance that wraps the running task.
        killed_flag: Flag to signal that the task was killed.
    """
    queue = make_task_key(task_id, TASK_COMMANDS_QUEUE)

    while True:
        logging.info("Waiting for messages on queue: %s", queue)
        element = redis_conn.brpop(queue)
        logging.info("Received message: %s", element)

        # If no kill message is received and the client is unblocked because
        # it is no longer required to wait for a message on the queue,
        # brpop returns None. Handle that case by returning from the function
        # without doing anything.
        if element is None:
            return

        content = element[1]

        if content == KILL_MESSAGE:
            logging.info("Received kill message. Killing task.")
            executer.terminate()
            logging.info("Task killed.")

            # set flag so that the main thread knows the task was killed
            killed_flag.set()
            return

        elif content == ENABLE_LOGGING_STREAM_MESSAGE:
            executer.loki_logger.enable()
            logging.info("Logging stream enabled.")

        elif content == DISABLE_LOGGING_STREAM_MESSAGE:
            executer.loki_logger.disable()
            logging.info("Logging stream disabled.")


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
        redis: Connection to Redis.
        docker_client: Docker client.
        docker_images: Mapping from executer_type to Docker image to use
            for executing the task.
        artifact_filesystem: Shared location with the Web API.
        executer_uuid: UUID of the executer that handles the requests.
            Used for event logging purposes.
        event_logger: Object to log events to a Redis stream.
        shared_dir_host: Path to the directory shared with the executer-tracker
            container on the host machine.
        shared_dir_local: Path to the directory shared with the
            executer-tracker container inside the container.
        task_id: ID of the task that is currently being executed. If
            no task is being executed, this attribute is None.
    """

    def __init__(
        self,
        redis_connection: redis.Redis,
        executers_config: Dict[str, config.ExecuterConfig],
        filesystem: fsspec.spec.AbstractFileSystem,
        artifact_store_root: str,
        executer_uuid: UUID,
        workdir: str,
        mpi_config: executers.MPIConfiguration,
    ):
        self.redis = redis_connection
        self.filesystem = filesystem
        self.artifact_store_root = artifact_store_root
        self.executer_uuid = executer_uuid
        self.event_logger = RedisStreamEventLoggerSync(self.redis, "events")
        self.executers_config = executers_config
        self.task_id = None
        self.workdir = workdir
        self.loki_logger = None
        self.mpi_config = mpi_config

        # If a share path for MPI is set, use it as the working directory.
        if self.mpi_config.share_path is not None:
            self.workdir = self.mpi_config.share_path

    def is_task_running(self) -> bool:
        """Checks if a task is currently running."""
        return self.task_id is not None

    def _log_task_picked_up(self):
        """Log that a task was picked up by the executer."""
        assert self.task_id is not None
        self.event_logger.log(
            events.TaskPickedUp(
                id=self.task_id,
                machine_id=self.executer_uuid,
            ))

    def _log_task_work_started(self):
        assert self.task_id is not None
        self.event_logger.log(
            events.TaskWorkStarted(
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
        self.task_dir_remote = os.path.join(self.artifact_store_root,
                                            request["task_dir"])
        self.current_task_executer_config = self.executers_config[
            request["executer_type"]]
        self.loki_logger = loki.LokiLogger(
            task_id=self.task_id,
            project_id=self.project_id,
        )

        self._log_task_picked_up()

        self.task_workdir = self._setup_working_dir(self.task_dir_remote)

        self.event_logger.log(
            events.TaskWorkStarted(
                id=self.task_id,
                machine_id=self.executer_uuid,
            ))
        exit_code, task_killed = self._execute_request(request,)
        logging.info("Task killed: %s", str(task_killed))

        event = events.TaskWorkFinished(
            id=self.task_id,
            machine_id=self.executer_uuid,
        )

        self.event_logger.log(event)

        output_size_b = self._pack_output()

        new_status = task_status.TaskStatusCode.SUCCESS.value
        if exit_code != 0:
            new_status = task_status.TaskStatusCode.FAILED.value
        if task_killed:
            new_status = task_status.TaskStatusCode.KILLED.value

        self.event_logger.log(
            events.TaskOutputUploaded(
                id=self.task_id,
                machine_id=self.executer_uuid,
                output_size_b=output_size_b,
                new_status=new_status,
            ))

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

        input_zip_path_remote = os.path.join(task_dir_remote,
                                             utils.INPUT_ZIP_FILENAME)

        files.download_and_extract_zip_archive(
            self.filesystem,
            input_zip_path_remote,
            task_workdir,
        )

        return task_workdir

    def _log_stdout(self):
        stdout_path_local = os.path.join(self.task_workdir, utils.OUTPUT_DIR,
                                         "artifacts/stdout.txt")
        stdout_path_remote = os.path.join(self.task_dir_remote,
                                          "stdout_live.txt")
        if stdout_path_local is not None and stdout_path_remote is not None:
            if os.path.exists(stdout_path_local):
                with self.filesystem.open(stdout_path_remote, "wb") as std_file:
                    with open(stdout_path_local, "rb") as f_src:
                        std_file.write(f_src.read())

    def _execute_request(
        self,
        request,
    ) -> Tuple[int, bool]:
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
        redis_client_id = self.redis.client_id()

        task_killed_flag = threading.Event()
        thread = threading.Thread(
            target=redis_command_msg_catcher,
            args=(self.redis, self.task_id, executer, task_killed_flag),
            daemon=True,
        )

        thread.start()
        exit_code = 0
        try:
            executer.run()
        except Exception as e:  # noqa: BLE001
            logging.error("Exception while running executer: %s", str(e))
            exit_code = 1

        logging.info("Tracker finished with exit code: %s", str(exit_code))
        self.redis.client_unblock(redis_client_id)
        thread.join()
        logging.info("Message catcher thread stopped.")

        return exit_code, task_killed_flag.is_set()

    def _pack_output(self) -> int:
        """Compress outputs and store them in the shared drive.

        Args:
            task_dir_remote: Path to the directory with the task's files. Path
                is relative to "artifact_filesystem".
            working_dir_local: Working directory of the executer that performed
                the task.

        Returns:
            Path to the zip file.
        """
        # Compress outputs, storing them in the shared drive
        output_dir = os.path.join(self.task_workdir, utils.OUTPUT_DIR)
        if not os.path.exists(output_dir):
            return 0

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_zip_path_local = os.path.join(tmp_dir,
                                                 utils.OUTPUT_ZIP_FILENAME)

            files.make_zip_archive(output_zip_path_local, output_dir)

            output_archive_size_b = os.path.getsize(output_zip_path_local)

            output_zip_path_remote = os.path.join(self.task_dir_remote,
                                                  utils.OUTPUT_ZIP_FILENAME)

            files.upload_file(self.filesystem, output_zip_path_local,
                              output_zip_path_remote)

            logging.info("Uploaded output zip to: %s", output_zip_path_remote)

        return output_archive_size_b

    def _cleanup(self):
        """Cleanup after task execution.

        Deletes the working directory of the task.

        Args:
            working_dir_local: Working directory of the executer that performed
                the task.
        """
        logging.info("Cleaning up working directory: %s", self.task_workdir)
        shutil.rmtree(self.task_workdir)

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

        container_image = self.current_task_executer_config.image

        return executer_class(
            self.task_workdir,
            container_image,
            copy.deepcopy(self.mpi_config),
            self.loki_logger,
        )
