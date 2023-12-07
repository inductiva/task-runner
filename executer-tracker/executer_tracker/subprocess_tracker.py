"""Module that defines the SubprocessTracker class."""
import os
import shlex
import signal
import subprocess
import psutil
import time

from absl import logging


class SubprocessTracker:
    """This is the embryo of the Subprocess Tracker Class."""

    spawn_time = None
    command_line = None
    subproc = None

    def __init__(
        self,
        command_line,
        working_dir,
    ):
        logging.info("Creating task tracker for \"%s\".", command_line)
        self.command_line = command_line
        self.working_dir = working_dir

    def run(self):
        """This is the main loop, where we execute the command and wait."""
        assert isinstance(self.command_line, str)

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
        except Exception as exception:  # pylint: disable=broad-except
            logging.warning("Caught exception \"%s\". Exiting gracefully",
                            exception)
            self.exit_gracefully()

    def wait(
        self,
        period_secs=1,
        periodic_callback=None,
    ) -> int:
        assert isinstance(self.subproc, subprocess.Popen)
        assert isinstance(self.spawn_time, float)

        # poll() method checks if child process has terminated.
        # While the process is running poll() returns None.
        try:
            while (exit_code := self.subproc.poll()) is None:
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

                # TODO(luispcunha): With the current implementation, the
                # resource usage is not being logged to the expected file
                # in the bucket while the simulation is running.
                if periodic_callback is not None:
                    periodic_callback()

                time.sleep(period_secs)

        except Exception as exception:  # pylint: disable=broad-except
            logging.warning("Caught exception \"%s\". Exiting gracefully",
                            exception)
            self.exit_gracefully()
            return -1

        logging.info("Process %d exited with exit code %d.", self.subproc.pid,
                     exit_code)

        return exit_code

    def exit_gracefully(self):
        """Ensures we kill the subprocess after signals or exceptions."""
        if not isinstance(self.subproc, subprocess.Popen):
            raise RuntimeError("subproc is not a subprocess.Popen object.")

        logging.info("Sending SIGTERM to PID %d", self.subproc.pid)

        if self.subproc:
            os.killpg(os.getpgid(self.subproc.pid), signal.SIGTERM)

        return self.subproc.poll()
