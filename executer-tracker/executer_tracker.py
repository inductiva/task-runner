"""
Simple example of a program that listens to events published to a REDIS STREAM.
If the stream already contains some items, it will gradually get each of them
and print to stdout. Then it will block on new content being added, and print
new items as they arrive to the stream.

Usage:
  python stream_listener.py --redis_stream all_requests
"""

import os
import shlex
import shutil
# import signal
import subprocess
import zipfile
import time
import json

from absl import app
from absl import flags
from absl import logging

import psutil
from redis import Redis

FLAGS = flags.FLAGS

flags.DEFINE_string("redis_stream", "all_requests",
                    "Name of the Redis Stream to subscribe to.")


def make_task_key(task_id: str, attribute: str) -> str:
    """
    Auxiliary function to generate Redis key to acess a given task attribute.
    Args:
        id: Redis key
        attribute: name of the task attribute we want to get
    """
    return f"task:{task_id}:{attribute}"


class SubprocessTracker:
    """This is the embryo of the Subprocess Tracker Class."""

    spawn_time = None
    command_line = None
    subproc = None
    ps_process = None

    def __init__(self, command_line, working_dir):
        # For now we just get the command line. There could be
        # other interesting arguments/parameters such as environment vars.
        # For example, Popen receive param env - eg. env={"PATH": "/usr/bin"}

        logging.info("Creating task tracker for \"%s\".", command_line)
        self.command_line = command_line
        self.working_dir = working_dir
        # Set up signal catcher by redirecting SIGINT and SIGTERM to
        # the class function signal_catcher(signal_catcher(self, *args)
        # SIGINT is keyboard INTerrupt. SIGTERM is to terminate (-9)
        # Note: SIGKILL cannot be intercepted.

        # Removing the signal catcher for now
        # signal.signal(signal.SIGINT, self.signal_catcher)
        # signal.signal(signal.SIGTERM, self.signal_catcher)

    def run(self):
        """This is the main loop, where we execute the command and wait.
        For now we are piping stdout and stderr to /dev/null
        This should be parametrized, taking into account that
        if we pipe these steams here we will need to deal with them.
        """
        logging.info("Spawning subprocess for \"%s\".", self.command_line)
        self.spawn_time = time.perf_counter()

        # pylint: disable=broad-except
        try:
            # pylint: disable=consider-using-with
            self.subproc = subprocess.Popen(
                shlex.split(self.command_line),
                cwd=self.working_dir,
                # stdout=subprocess.DEVNULL,
                # stderr=subprocess.DEVNULL,
            )
            # pylint: enable=consider-using-with

            logging.info("Started process with PID %d.", self.subproc.pid)
            process_status = psutil.Process(self.subproc.pid)

            # poll() method checks if child process has terminated.
            # While the process is running poll() returns None.
            while not self.subproc.poll():
                logging.info("Status of subprocess %d: %s", self.subproc.pid,
                             process_status.status())
                logging.info("Time running: %d secs",
                             time.perf_counter() - self.spawn_time)
                logging.info("Current Mem usage: %s",
                             process_status.memory_info())
                logging.info("Current CPU usage: %s",
                             process_status.cpu_times())
                children_procs = process_status.children(recursive=True)
                logging.info("Children spawned: %s", children_procs)

                time.sleep(1)

        ## This situation may occur when the we call process_status.* on a
        ## process that has already finished.
        except psutil.NoSuchProcess as no_such_process_exception:
            logging.warning("Caught exception \"%s\"",
                            no_such_process_exception)
            logging.warning("Did the process already finish?")
            return self.subproc.poll()

        except Exception as exception:
            logging.warning("Caught exception \"%s\". Exiting gracefully",
                            exception)
            self.exit_gracefully()
            return -1
        # pylint: enable=broad-except

        logging.info("Process %d exited with exit code %d.", self.subproc.pid,
                     self.subproc.poll())
        return self.subproc.poll()

    # pylint: disable=unused-argument
    def signal_catcher(self, *args):
        """Handler to catch signals sent to this process."""
        logging.info("Got SIGTERM/SIGINT signal.")
        self.exit_gracefully()

    # pylint: enable=unused-argument

    def exit_gracefully(self):
        """Ensures we kill the subprocess after signals or exceptions."""
        logging.info("Sending SIGKILL to PID %d", self.subproc.pid)
        # For now we just kill the process we directly spawned
        # i.e we are not cleaning up its children (yet).
        if self.subproc:
            self.subproc.kill()
        return self.subproc.poll()


def monitor_redis_stream(redis_connection, stream_name, last_stream_id=0):
    """

    Args:
        redis_connection: connection to Redis server
        stream_name: name of Redis Stream
        last_id: unique id of the stream item you want to start
            listing from (every item after that will be logged).
            Redis stream ids are sorted, based on timestamps.
            Default: 0 (will log the whole stream).
    """
    sleep_ms = 0  # 0ms means block forever
    artifact_dest = os.getenv("ARTIFACT_STORE")  # drive shared with web_api

    while True:
        try:
            resp = redis_connection.xread(
                {stream_name: last_stream_id},
                count=1,  # reads one item at a time.
                block=sleep_ms)
            if resp:
                _, messages = resp[0]
                last_stream_id, request = messages[0]
                logging.info("REDIS ID: %s", str(last_stream_id))
                logging.info("      --> %s", str(request))

                request_id = request["id"]

                # This just checks the request status.
                # If it is different than submitted,
                # it means it has already been processed.
                # Right now, this avoids processing the same request twice
                request_status = redis_connection.get(
                    make_task_key(request_id, "status"))
                logging.info("Status of request %s: %s", request_id,
                             request_status)

                # second check is because the request may be received
                # before the web api sets the request as submitted
                # solution could be making the web api submitting the
                # request and setting it as submitted in a transaction
                if request_status != "submitted" and request_status is not None:
                    continue

                # Create working dir for the script that will accomplish
                # the received request
                # The uniqueness of the working dir is guaranteed
                # by using the ID generated by Redis
                working_dir = os.path.join(os.path.abspath(os.sep),
                                           "working_dir", request_id)
                os.makedirs(working_dir)

                # If "params" is not in the request, it means
                # that the input is a zip file
                if "params" not in request:
                    input_zip_path = os.path.join(artifact_dest, "inputs",
                                                  f"{request_id}.zip")

                    # Extract files to the working_dir
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

                method_name = request["method"].split(".")[-1]
                method_path = os.path.join("/scripts", f"{method_name}.py")
                command_line = f"python {method_path}"

                tracker = SubprocessTracker(
                    working_dir=working_dir,
                    command_line=command_line,
                )

                # Mark task as started
                redis_connection.set(make_task_key(request_id, "status"),
                                     "started")
                exit_code = tracker.run()

                logging.info("Tracker returned exit code %s", str(exit_code))

                # Read outputs from file generated by output
                output_path = os.path.join(working_dir, "output.json")
                with open(output_path, encoding="UTF-8") as fp:
                    output_json = fp.read()

                output_dict = json.loads(output_json)
                logging.info("Worker script outputs: %s", output_dict)

                # Copying generated files to drive shared with web api
                for key, value in output_dict.items():
                    if key.endswith("_path"):
                        src_path = os.path.join(working_dir, value)
                        dst_dir = os.path.join(artifact_dest, request_id)
                        os.makedirs(dst_dir, exist_ok=True)
                        dst_path = os.path.join(dst_dir, value)
                        shutil.copyfile(src_path, dst_path)
                        logging.info("Copied %s from %s to %s", value, src_path,
                                     dst_path)

                # Assuming everything ran successfully for now

                # Write result to Redis
                # An Hash is a Redis datatype that is
                # suitable for storing dictionaries
                # Mapping specifies a dictionary of multiple key,
                # values as elements of the Hash
                # corresponding to the current job's ID
                # An alternative could be storing the results as a JSON string
                redis_connection.hset(make_task_key(request_id, "output"),
                                      mapping=output_dict)
                logging.info("Stored outputs of job with ID %s in Redis",
                             request_id)

                # Mark task as finished successfully
                out = redis_connection.set(make_task_key(request_id, "status"),
                                           "success")
                logging.info("Marking task as successful: %s", out)

        except ConnectionError as e:
            logging.info("ERROR REDIS CONNECTION: %s", str(e))


def main(_):
    redis_hostname = os.getenv("REDIS_HOSTNAME")
    redis_port = os.getenv("REDIS_PORT", "6379")

    redis_conn = Redis(redis_hostname,
                       redis_port,
                       retry_on_timeout=True,
                       decode_responses=True)
    monitor_redis_stream(redis_conn, FLAGS.redis_stream)


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
