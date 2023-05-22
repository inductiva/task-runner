"""Module that defines the TaskRequestHandler class.

The TaskRequestHandler class serves as a handler of task requests, i.e.,
handles the logic related to setting up the working_dir of an executer,
launching said executer, and providing the outputs to the Web API.
Note that, currently, request consumption is blocking.
"""
import os
import shutil
import threading
from absl import logging
import utils
from utils import make_task_key
from utils.files import extract_zip_archive
from subprocess_tracker import SubprocessTracker
from task_status import TaskStatusCode
from inductiva_api import events
from inductiva_api.events import EventStore


def redis_kill_msg_catcher(redis, task_id, subprocess_tracker, killed_flag):
    """Function that waits for the kill message and kills the running job."""
    queue = make_task_key(task_id, "events")
    logging.info("Waiting for kill message on queue.")

    while True:
        logging.info("Waiting for kill message on queue.")
        element = redis.brpop(queue)
        logging.info("Received message \"%s\" from the Web API", element)
        # If no kill message is received and the client is unblocked,
        # brpop returns None.
        if element is None:
            return

        content = element[1]
        if content == "kill":
            subprocess_tracker.exit_gracefully()
            killed_flag.set()
            return


class TaskRequestHandler:
    """Class that implements the request consumption logic.

    The TaskRequestHandler represents a stateful handler of requests. Its
    intended usage is within a loop where requests are listened for.
    After a request arrives, it is passed to an instance of TaskRequestHandler
    for blocking execution of the request. The TaskRequestHandler defines
    the __call__ method, so passing a request to an instance of
    TaskRequestHandler is a call like `request_handler(request)`, where
    `request_handler` is the TaskRequestHandler instance and `request` is
    the request for consumption.

    Attributes:
        redis: Connection to Redis.
        artifact_dest: Shared directory with the Web API.
    """
    WORKING_DIR_ROOT = "working_dir"

    def __init__(self, redis_connection, artifact_dest, executer_name):
        """Initialize an instance of the TaskRequestHandler class."""
        self.redis = redis_connection
        self.artifact_dest = artifact_dest
        self.executer_name = executer_name
        self.event_store = EventStore("events")
        self.current_task_id = None

        self.working_dir_root = os.path.join(os.path.abspath(os.sep),
                                             self.WORKING_DIR_ROOT)
        os.makedirs(self.working_dir_root, exist_ok=True)

    def update_task_status(self, task_id, status: TaskStatusCode):
        msg_queue_key = make_task_key(task_id, "status_updates")

        with self.redis.pipeline(transaction=True) as pipe:
            pipe = pipe.set(make_task_key(task_id, "status"), status.value)
            pipe = pipe.lpush(msg_queue_key, status.value)
            _ = pipe.execute()

        logging.info("Updated task status to %s.", status.value)

    def update_task_attribute(self, task_id, attribute, value):
        self.redis.set(make_task_key(task_id, attribute), value)
        logging.info("Updated task %s to %s.", attribute, value)

    def get_task_status(self, task_id) -> TaskStatusCode:
        task_status = self.redis.get(make_task_key(task_id, "status"))
        return TaskStatusCode(task_status)

    def build_working_dir(self, request) -> str:
        """Create the working directory for a given request.

        Create working dir for the script that will accomplish the request.
        The uniqueness of the working dir is guaranteed by using the task id
        in the directory name.

        Args:
            request: Request that will use the created working dir.

        Returns:
            Path of the created working directory.
        """
        working_dir = os.path.join(self.working_dir_root, request["id"])
        os.makedirs(working_dir)
        return working_dir

    def build_command(self, request) -> str:
        """Build Python command to run a requested task.

        NOTE: this method is a candidate for improvement.

        Args:
            request: Request for which to build a command.

        Returns:
            Python command to execute received request.
        """

        method_to_script = {
            "linalg.eigs": "/scripts/run_eigensolver.py",
            "math.matmul": "/scripts/matmul.py",
            "math.sum": "/scripts/sum.py",
            "test.sleep": "/scripts/sleep.py",
            "sph.splishsplash.run_simulation": "/scripts/simulation.py",
            "sph.dualsphysics.run_simulation": "/scripts/simulation.py",
            "sw.swash.run_simulation": "/scripts/simulation.py",
            "sw.xbeach.run_simulation": "/scripts/simulation.py",
            "fvm.openfoam.run_simulation": "/scripts/simulation.py",
            "md.gromacs.run_simulation": "/scripts/simulation.py",
        }
        method = request["method"]

        return f"python {method_to_script[method]}"

    def setup_working_dir(self, request):
        """Setup the working directory for an executer.

        This method performs initial setup of the working directory
        for an executer. More specifically, it ensures that it exists
        and contains the necessary input files.

        There are two different scenarios:
            1. A ZIP with the full input is provided, so all that's needed
            is to extract the ZIP to the correct place.

            2. The request contains a json specifying the full request,
            so setting up the working dir requires writting the JSON
            to the correct place.

        Args:
            request: Request that will run in the working directory. The
                presence of the field "params" in the request dict defines
                which of the above described scenarios is followed.
                If "params" exists, scenario 2 is used. If not, then it is
                assumed that an input ZIP already exists.
        """
        working_dir = self.build_working_dir(request)

        input_zip_path = os.path.join(self.artifact_dest, request["id"],
                                      utils.INPUT_ZIP_FILENAME)

        extract_zip_archive(
            zip_path=input_zip_path,
            dest=working_dir,
        )

        logging.info("Extracted input zip %s to %s", input_zip_path,
                     working_dir)

        return working_dir

    def execute_request(self, request, task_id, working_dir):
        """Execute the request, return the exit code of the executer script.

        NOTE: this launchs a second thread to listen for possible "kill"
        messages from the API.
        """
        tracker = SubprocessTracker(working_dir=working_dir,
                                    command_line=self.build_command(request),
                                    logs_path=os.path.join(
                                        self.artifact_dest, task_id,
                                        utils.LOGS_FILENAME))

        self.redis_client_id = self.redis.client_id()

        task_killed_flag = threading.Event()
        thread = threading.Thread(
            target=redis_kill_msg_catcher,
            args=(self.redis, task_id, tracker, task_killed_flag),
            daemon=True,
        )

        self.update_task_status(task_id, TaskStatusCode.STARTED)
        self.event_store.log_sync(
            self.redis,
            events.TaskStarted(
                id=task_id,
                executer=self.executer_name,
                status=TaskStatusCode.STARTED.value,
            ),
        )

        thread.start()
        exit_code = tracker.run()
        logging.info("Tracker returned exit code %s.", str(exit_code))

        self.redis.client_unblock(self.redis_client_id)

        thread.join()
        logging.info("Message catcher thread stopped.")

        return exit_code, task_killed_flag.is_set()

    def pack_output(self, task_id, working_dir):
        """Compress outputs and store them in the shared drive.

        Args:
            task_id: ID of task to which the outputs are related. Required
                as the ID is necessary to resolve the path where the outputs
                should be stored in the shared drive.
            working_dir: Working directory of the executer that performed
                the task.

        Returns:
            Path to the zip file.
        """
        # Compress outputs, storing them in the shared drive
        output_dir = os.path.join(working_dir, utils.OUTPUT_DIR)

        output_zip_name = os.path.join(self.artifact_dest, task_id,
                                       utils.OUTPUT_DIR)

        output_zip_path = shutil.make_archive(output_zip_name, "zip",
                                              output_dir)

        logging.info("Compressed output to %s", output_zip_path)

        return output_zip_path

    def __call__(self, request):
        """Execute the task described by the request.

        Note that this method is blocking. While the task is being processed
        via the SubprocessTracker class, a thread is set to listen to a Redis
        queue, in which a "kill" message may be received. If the message is
        received, then the subprocess running the requested task is killed.

        Args:
            request: Request describing the task to be executed.
        """
        task_id = request["id"]
        self.current_task_id = task_id

        self.update_task_attribute(task_id, "executer_name", self.executer_name)

        working_dir = self.setup_working_dir(request)

        exit_code, task_killed = \
            self.execute_request(request, task_id, working_dir)

        self.pack_output(task_id, working_dir)

        self.current_task_id = None

        if task_killed:
            self.event_store.log_sync(
                self.redis,
                events.TaskKilled(
                    id=task_id,
                    status=TaskStatusCode.KILLED.value,
                ),
            )
            self.update_task_status(task_id, TaskStatusCode.KILLED)
            return

        new_status = TaskStatusCode.FAILED if exit_code else \
            TaskStatusCode.SUCCESS
        self.update_task_status(task_id, new_status)
        self.event_store.log_sync(
            self.redis,
            events.TaskCompleted(id=task_id, status=new_status.value),
        )

    def is_processing(self) -> bool:
        return self.current_task_id is not None
