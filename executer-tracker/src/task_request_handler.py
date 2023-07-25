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
from uuid import UUID

import utils
from absl import logging
from inductiva_api import events
from inductiva_api.events import RedisStreamEventLoggerSync
from inductiva_api.task_status import TaskStatusCode
from pyarrow import fs
from utils import make_task_key
from utils import files
from task_tracker import TaskTracker


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
    queue = make_task_key(task_id, "events")

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
        docker_images: Dict[str, str],
        artifact_filesystem: fs.FileSystem,
        executer_uuid: UUID,
        shared_dir_host: str,
        shared_dir_local: str,
    ):
        self.docker = docker_client
        self.redis = redis_connection
        self.artifact_filesystem = artifact_filesystem
        self.executer_uuid = executer_uuid
        self.event_logger = RedisStreamEventLoggerSync(self.redis, "events")
        self.docker_images = docker_images
        self.shared_dir_host = shared_dir_host
        self.shared_dir_local = shared_dir_local
        self.task_id = None

    def is_task_running(self) -> bool:
        """Checks if a task is currently running."""
        return self.task_id is not None

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

        working_dir_local, working_dir_host = self._setup_working_dir(
            task_dir_remote)
        exit_code, task_killed = self._execute_request(request,
                                                       working_dir_host)
        self._pack_output(task_dir_remote, working_dir_local)

        if task_killed:
            self.event_logger.log(events.TaskKilled(id=self.task_id),)
            return

        if exit_code:
            new_status = TaskStatusCode.FAILED
        else:
            new_status = TaskStatusCode.SUCCESS

        self.event_logger.log(
            events.TaskCompleted(id=self.task_id, status=new_status))

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

    def _execute_request(self, request, working_dir_host) -> Tuple[int, bool]:
        """Execute the request.

        This uses a second thread to listen for possible "kill" messages from
        the API.

        Returns:
            Tuple of the exit code of the task and a bool representing if the
            task was killed.
        """
        assert self.task_id is not None, (
            "'_execute_request' called without a task ID.")

        image = self.docker_images[request["executer_type"]]

        tracker = TaskTracker(
            docker_client=self.docker,
            image=image,
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

        self.event_logger.log(
            events.TaskStarted(
                id=self.task_id,
                executer_id=self.executer_uuid,
            ))

        thread.start()
        tracker.run()

        exit_code = tracker.wait()
        logging.info("Tracker finished with exit code: %s", str(exit_code))
        self.redis.client_unblock(redis_client_id)
        thread.join()
        logging.info("Message catcher thread stopped.")

        return exit_code, task_killed_flag.is_set()

    def _pack_output(self, task_dir_remote, working_dir_local):
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
        method_to_script = {
            "linalg.eigs":
                "/scripts/run_eigensolver.py",
            "math.matmul":
                "/scripts/matmul.py",
            "math.sum":
                "/scripts/sum.py",
            "test.sleep":
                "/scripts/sleep.py",
            "sph.splishsplash.run_simulation":
                "/scripts/simulation.py",
            "sph.dualsphysics.run_simulation":
                "/scripts/simulation.py",
            "sw.swash.run_simulation":
                "/scripts/simulation.py",
            "sw.xbeach.run_simulation":
                "/scripts/simulation.py",
            "fvm.openfoam.run_simulation":
                "/scripts/simulation.py",
            "windtunnel.openfoam.run_simulation":
                "/scripts/windtunnel_simulation.py",
            "md.gromacs.run_simulation":
                "/scripts/simulation.py",
        }
        method = request["method"]

        return f"python {method_to_script[method]}"
