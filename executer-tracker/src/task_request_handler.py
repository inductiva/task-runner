"""Module that defines the TaskRequestHandler class.

The TaskRequestHandler class serves as a handler of task requests, i.e.,
handles the logic related to setting up the working_dir of an executer,
launching said executer, and providing the outputs to the Web API.
Note that, currently, request consumption is blocking.
"""
import os
import shutil
from absl import logging
import time
import utils
from utils import make_task_key
from utils.files import extract_zip_archive, write_input_json
from subprocess_tracker import SubprocessTracker
from concurrent.futures import ThreadPoolExecutor


def redis_msg_catcher(redis, queue, subprocess_tracker):
    _, content = redis.brpop(queue)
    logging.info("Received message \"%s\" from the Web API", content)

    if content == "kill":
        return subprocess_tracker.exit_gracefully()


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
        working_dir_root: Directory where executer working dirs are created.
        artifact_dest: Shared directory with the Web API.
    """

    def __init__(self, redis_connection, working_dir_root, artifact_dest):
        """Initialize an instance of the TaskRequestHandler class."""
        self.redis = redis_connection
        self.working_dir_root = working_dir_root
        self.artifact_dest = artifact_dest

        self.thread_pool = ThreadPoolExecutor(max_workers=1)

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
            "sw.swash.run_simulation": "/scripts/simulation.py",
        }
        method = request["method"]

        return f"python {method_to_script[method]}"

    def setup_working_dir(self, request, working_dir):
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
            working_dir: Path in which to setup the working directory.
        """
        if "params" in request:
            input_json_path = write_input_json(working_dir, request["params"])
            logging.info("Wrote JSON input to %s", input_json_path)
            return

        input_zip_path = os.path.join(self.artifact_dest, request["id"],
                                      utils.INPUT_ZIP_FILENAME)

        extract_zip_archive(
            zip_path=input_zip_path,
            dest=working_dir,
        )

        logging.info("Extracted input zip %s to %s", input_zip_path,
                     working_dir)

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

        Note that this method is blocking.

        Args:
            request: Request describing the task to be executed.
        """
        task_id = request["id"]

        task_status = self.redis.get(make_task_key(task_id, "status"))

        # Check if task status is submitted. The task status could be
        # "killed", in which case it is not supposed to be executed
        if task_status != "submitted":
            return

        working_dir = self.build_working_dir(request)
        self.setup_working_dir(request, working_dir)

        tracker = SubprocessTracker(
            working_dir=working_dir,
            command_line=self.build_command(request),
        )

        # Mark task as started
        self.redis.set(make_task_key(task_id, "status"), "started")

        redis_client_id = self.redis.client_id()

        # Start thread that blocks while waiting for messages related to
        # the currently executing task
        msg_catcher_thread = self.thread_pool.submit(
            redis_msg_catcher,
            self.redis,
            make_task_key(task_id, "events"),
            tracker,
        )

        exit_code = tracker.run()
        logging.info("Tracker returned exit code %s", str(exit_code))

        # Unblock the connection that's blocked waiting for a kill message
        self.redis.client_unblock(redis_client_id)

        self.pack_output(task_id, working_dir)

        # NOTE: Assuming everything ran successfully for now
        # Mark task as finished successfully
        self.redis.set(make_task_key(task_id, "status"), "success")
        logging.info("Marked task as successful")

        # Check if message catcher thread stopped running
        done = False
        while not done:
            done = msg_catcher_thread.done()
            logging.info("Message catcher thread stopped: %s", done)
            time.sleep(0.1)
