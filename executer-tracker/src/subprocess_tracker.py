"""Module that defines the SubprocessTracker class."""
import os
import shlex
import signal
import subprocess
import psutil
import time

from absl import logging
from utils import config


class SubprocessTracker:
    """This is the embryo of the Subprocess Tracker Class."""

    spawn_time = None
    command_line = None
    subproc = None
    ps_process = None

    def __init__(
        self,
        command_line,
        working_dir,
    ):
        logging.info("Creating task tracker for \"%s\".", command_line)
        self.command_line = command_line
        self.working_dir = working_dir

    def run(self):
        """This is the main loop, where we execute the command and wait.
        For now we are piping stdout and stderr to /dev/null
        This should be parametrized, taking into account that
        if we pipe these steams here we will need to deal with them.
        """
        logging.info("Spawning subprocess for \"%s\".", self.command_line)
        self.spawn_time = time.perf_counter()

        try:
            args = shlex.split(self.command_line)
            # pylint: disable=consider-using-with
            self.subproc = subprocess.Popen(
                args,
                cwd=self.working_dir,
                start_new_session=True,
            )

            # pylint: enable=consider-using-with
            logging.info("Started process with PID %d.", self.subproc.pid)
        except Exception as exception:
            logging.warning("Caught exception \"%s\". Exiting gracefully",
                            exception)
            self.exit_gracefully()

    def wait(self):

        # poll() method checks if child process has terminated.
        # While the process is running poll() returns None.
        try:
            while not self.subproc.poll():
                process_status = psutil.Process(self.subproc.pid)

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

    def exit_gracefully(self):
        """Ensures we kill the subprocess after signals or exceptions."""
        logging.info("Sending SIGTERM to PID %d", self.subproc.pid)

        if self.subproc:
            os.killpg(os.getpgid(self.subproc.pid), signal.SIGTERM)

        return self.subproc.poll()
