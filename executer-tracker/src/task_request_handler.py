"""Handle execution of received task requests.

The TaskRequestHandler class implements the execution flow of a task, i.e.,
handles the logic related to setting up the working directory of an executer,
launching said executer, and providing the outputs to the Web API.
Note that, currently, request consumption is blocking.
"""
import os
import shutil
import tempfile
import threading
from typing import Dict, Tuple
import docker
import redis
import json
from uuid import UUID
from google.cloud import storage
import google

import utils
from absl import logging
from inductiva_api import events
from inductiva_api.events import RedisStreamEventLoggerSync
from inductiva_api.task_status import task_status
from pyarrow import fs
from utils import make_task_key
from utils import files, config
from task_tracker import TaskTracker

TASK_COMMANDS_QUEUE = "commands"


def redis_kill_msg_catcher(
    redis_conn: redis.Redis,
    task_id: str,
    task_tracker: TaskTracker,
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
        logging.info("Waiting for kill message on queue: %s", queue)
        element = redis_conn.brpop(queue)
        logging.info("Received message: %s", element)

        # If no kill message is received and the client is unblocked because
        # it is no longer required to wait for a message on the queue,
        # brpop returns None. Handle that case by returning from the function
        # without doing anything.
        if element is None:
            return

        content = element[1]
        if content == "kill":
            logging.info("Received kill message. Killing task.")
            task_tracker.kill()
            logging.info("Task killed.")

            # set flag so that the main thread knows the task was killed
            killed_flag.set()
            return


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
        docker_client: docker.DockerClient,
        executers_config: Dict[str, config.ExecuterConfig],
        artifact_filesystem: fs.FileSystem,
        executer_uuid: UUID,
        shared_dir_host: str,
        shared_dir_local: str,
        project_id=str,
    ):
        self.docker = docker_client
        self.redis = redis_connection
        self.artifact_filesystem = artifact_filesystem
        self.executer_uuid = executer_uuid
        self.event_logger = RedisStreamEventLoggerSync(self.redis, "events")
        self.executers_config = executers_config
        self.shared_dir_host = shared_dir_host
        self.shared_dir_local = shared_dir_local
        self.task_id = None
        self.project_id = project_id

    def is_task_running(self) -> bool:
        """Checks if a task is currently running."""
        return self.task_id is not None

    def _log_task_picked_up(self):
        """Log that a task was picked up by the executer.

        This gets the necessary information from the Docker image metadata
        (git commit hash, docker image digest), and logs an event with
        the information that this task was picked up by the machine and
        will be run with the Docker image with that information.
        """
        docker_image = self.current_task_executer_config.image

        executer_docker_image_digest = None
        executer_git_commit_hash = None
        executer_docker_image = self.docker.images.get(docker_image)
        if executer_docker_image is not None:
            if executer_docker_image.labels is not None:
                executer_git_commit_hash = executer_docker_image.labels.get(
                    "org.opencontainers.image.revision")
            if executer_docker_image.attrs is not None:
                executer_docker_image_digests = executer_docker_image.attrs.get(
                    "RepoDigests")
                if len(executer_docker_image_digests) > 0:
                    executer_docker_image_digest = \
                        executer_docker_image_digests[0]

        assert self.task_id is not None
        self.event_logger.log(
            events.TaskPickedUp(
                id=self.task_id,
                machine_id=self.executer_uuid,
                executer_git_commit_hash=executer_git_commit_hash,
                executer_docker_image_digest=executer_docker_image_digest,
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
        task_dir_remote = request["task_dir"]
        self.current_task_executer_config = self.executers_config[
            request["executer_type"]]

        self._log_task_picked_up()

        working_dir_local, working_dir_host = self._setup_working_dir(
            task_dir_remote)

        std_path = os.path.join(working_dir_local, utils.OUTPUT_DIR,
                                "artifacts/stdout.txt")
        resources_path = os.path.join(working_dir_local, utils.OUTPUT_DIR,
                                      "artifacts/resources_usage.txt")

        stdout_blob, resources_blob = self._get_storage_blob(task_dir_remote)

        self.event_logger.log(
            events.TaskWorkStarted(
                id=self.task_id,
                machine_id=self.executer_uuid,
            ))
        exit_code, task_killed = self._execute_request(
            request,
            working_dir_host,
            stdout_file=std_path,
            stdout_blob=stdout_blob,
            resources_file=resources_path,
            resources_blob=resources_blob)

        event = events.TaskWorkFinished(
            id=self.task_id,
            machine_id=self.executer_uuid,
        )

        self.event_logger.log(event)

        output_size_b = self._pack_output(task_dir_remote, working_dir_local)

        new_status = task_status.TaskStatusCode.SUCCESS.value
        if task_killed:
            new_status = task_status.TaskStatusCode.KILLED.value
        if exit_code != 0:
            new_status = task_status.TaskStatusCode.FAILED.value

        self.event_logger.log(
            events.TaskOutputUploaded(
                id=self.task_id,
                machine_id=self.executer_uuid,
                output_size_b=output_size_b,
                new_status=new_status,
            ))

        self._cleanup(working_dir_local)
        self.task_id = None

    def _setup_working_dir(self, task_dir_remote) -> Tuple[str, str]:
        """Setup the working directory for the task.

        Returns:
            Tuple of the local and host paths to the working directory,
            respectively. The local path is the path inside the container,
            and the host path is the path on the host machine.
        """
        assert self.task_id is not None, (
            "'_setup_working_dir' called without a task ID.")

        working_dir_local = os.path.join(self.shared_dir_local, self.task_id)
        working_dir_host = os.path.join(self.shared_dir_host, self.task_id)

        # Both vars point to the same directory (one is the path on the host
        # machine and the other is the path inside the container).
        os.makedirs(working_dir_local)

        input_zip_path_remote = os.path.join(task_dir_remote,
                                             utils.INPUT_ZIP_FILENAME)

        files.download_and_extract_zip_archive(
            self.artifact_filesystem,
            input_zip_path_remote,
            working_dir_local,
        )

        return working_dir_local, working_dir_host

    def _execute_request(self,
                         request,
                         working_dir_host,
                         stdout_file=None,
                         stdout_blob=None,
                         resources_blob=None,
                         resources_file=None) -> Tuple[int, bool]:
        """Execute the request.

        This uses a second thread to listen for possible "kill" messages from
        the API.

        Returns:
            Tuple of the exit code of the task and a bool representing if the
            task was killed.
        """
        assert self.task_id is not None, (
            "'_execute_request' called without a task ID.")

        tracker = TaskTracker(
            docker_client=self.docker,
            executer_config=self.current_task_executer_config,
            command=self._build_command(request),
            working_dir_host=working_dir_host,
        )
        redis_client_id = self.redis.client_id()

        task_killed_flag = threading.Event()
        thread = threading.Thread(
            target=redis_kill_msg_catcher,
            args=(self.redis, self.task_id, tracker, task_killed_flag),
            daemon=True,
        )

        thread.start()
        tracker.run()

        exit_code = tracker.wait(stdout_file, stdout_blob, resources_file,
                                 resources_blob)
        logging.info("Tracker finished with exit code: %s", str(exit_code))
        self.redis.client_unblock(redis_client_id)
        thread.join()
        logging.info("Message catcher thread stopped.")

        return exit_code, task_killed_flag.is_set()

    def _get_storage_blob(self, task_dir_remote):
        """Get Google Storage object class.

        Args:
            task_dir_remote: Path to the directory with the task's files. Path
                is relative to "artifact_filesystem".
        Returns:
            Blob object of stdout and resource file."""
        try:
            bucket_name = task_dir_remote.split("/", 1)[0]
            task_dir = task_dir_remote.split("/", 1)[1]

            storage_client = storage.Client(project=self.project_id)
            bucket = storage_client.bucket(bucket_name)
            stdout_blob = bucket.blob(os.path.join(task_dir, "stdout_live.txt"))
            resource_blob = bucket.blob(
                os.path.join(task_dir, "resource_usage.txt"))

            return stdout_blob, resource_blob

        except google.auth.exceptions.DefaultCredentialsError:
            logging.error("Failed to authenticate with Google Cloud.")
            return None, None

    def _pack_output(self, task_dir_remote, working_dir_local) -> int:
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
        output_dir = os.path.join(working_dir_local, utils.OUTPUT_DIR)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_zip_path_local = os.path.join(tmp_dir,
                                                 utils.OUTPUT_ZIP_FILENAME)

            files.make_zip_archive(output_zip_path_local, output_dir)

            output_archive_size_b = os.path.getsize(output_zip_path_local)

            output_zip_path_remote = os.path.join(task_dir_remote,
                                                  utils.OUTPUT_ZIP_FILENAME)

            files.upload_file(
                self.artifact_filesystem,
                output_zip_path_local,
                output_zip_path_remote,
            )

            logging.info(
                "Uploaded output zip to: %s",
                os.path.join(
                    self.artifact_filesystem.base_path,
                    output_zip_path_remote,
                ))

        return output_archive_size_b

    def _cleanup(self, working_dir_local):
        """Cleanup after task execution.

        Deletes the working directory of the task.

        Args:
            working_dir_local: Working directory of the executer that performed
                the task.
        """
        logging.info("Cleaning up working directory: %s", working_dir_local)
        shutil.rmtree(working_dir_local)

    def _build_command(self, request) -> str:
        """Build Python command to run a requested task.

        NOTE: this method is a candidate for improvement.

        Args:
            request: Request for which to build a command.

        Returns:
            Python command to execute received request.
        """
        with open("methods_to_script.json", "r", encoding="utf-8") as json_file:
            method_to_script = json.load(json_file)

        method = request["method"]

        return f"python {method_to_script[method]}"
