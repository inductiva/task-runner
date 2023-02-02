import os
import shutil
import zipfile
from absl import logging

from utils import make_task_key
from subprocess_tracker import SubprocessTracker


class RequestConsumer:

    def __init__(self, redis_connection, working_dir_root, artifact_dest):
        self.redis = redis_connection
        self.working_dir_root = working_dir_root
        self.artifact_dest = artifact_dest

    def build_working_dir(self, request) -> str:
        # Create working dir for the script that will accomplish
        # the received request
        # The uniqueness of the working dir is guaranteed
        # by using the task id
        working_dir = os.path.join(self.working_dir_root, request["id"])
        os.makedirs(working_dir)
        return working_dir

    def build_command(self, request) -> str:
        method_name = request["method"].split(".")[-1]
        method_path = os.path.join("/scripts", f"{method_name}.py")
        return f"python {method_path}"

    def setup_working_dir(self, request, working_dir):
        # If "params" is not in the request, it means
        # that the input is a zip file
        if "params" not in request:
            input_zip_path = os.path.join(self.artifact_dest, request["id"],
                                          "input.zip")

            # Extract files to the working_dir.
            # NOTE: it is expected that the input.json is
            # inside the zip file
            with zipfile.ZipFile(input_zip_path, "r") as zip_fp:
                zip_fp.extractall(working_dir)

            logging.info("Extracted input zip %s to %s", input_zip_path,
                         working_dir)
        else:
            # Create input json file
            input_json_path = os.path.join(working_dir, "input.json")
            with open(input_json_path, "w", encoding="UTF-8") as fp:
                fp.write(request["params"])

    def pack_output(self, task_id, working_dir):
        # Compress outputs, storing them in the shared drive
        output_dir = os.path.join(working_dir, "output")

        output_zip_name = os.path.join(self.artifact_dest, task_id, "output")
        output_zip_path = shutil.make_archive(output_zip_name, "zip",
                                              output_dir)

        logging.info("Compressed output to %s", output_zip_path)

        return output_zip_path

    def __call__(self, request):
        task_id = request["id"]

        request_status = self.redis.get(make_task_key(task_id, "status"))
        logging.info("Status of request %s: %s", task_id, request_status)

        if request_status != "submitted":
            return

        working_dir = self.build_working_dir(request)
        self.setup_working_dir(request, working_dir)

        tracker = SubprocessTracker(
            working_dir=working_dir,
            command_line=self.build_command(request),
        )

        # Mark task as started
        self.redis.set(make_task_key(task_id, "status"), "started")

        exit_code = tracker.run()
        logging.info("Tracker returned exit code %s", str(exit_code))

        self.pack_output(task_id, working_dir)

        # Assuming everything ran successfully for now

        # Mark task as finished successfully
        self.redis.set(make_task_key(task_id, "status"), "success")
        logging.info("Marked task as successful")
