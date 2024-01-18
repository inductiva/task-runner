"""Module that defines the SubprocessTracker class."""
from typing import List
import os
import signal
import subprocess
import psutil
import time

from absl import logging


class SubprocessTracker:
    """Class used to launch and manage a subprocess."""

    spawn_time = None
    command_line = None
    subproc = None

    def __init__(
        self,
        args: List[str],
        working_dir,
        stdout,
        stderr,
        stdin,
        loki_logger,
    ):
        logging.info("Creating task tracker for \"%s\".", args)
        self.args = args
        self.working_dir = working_dir
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = stdin
        self.loki_logger = loki_logger

    def run(self):
        """This is the main loop, where we execute the command and wait."""
        logging.info("Spawning subprocess for \"%s\".", self.args)
        self.spawn_time = time.perf_counter()

        try:
            # pylint: disable=consider-using-with
            self.subproc = subprocess.Popen(
                self.args,
                cwd=self.working_dir,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=self.stdin,
                shell=False,
            )
            if self.subproc.stdout is not None:
                for line in self.subproc.stdout:
                    log_message = line.decode("utf-8").strip()
                    self.loki_logger.log_text(log_message, io_type="std_out")
                    self.stdout.write(log_message)
                    self.stdout.flush()
                    self.stdout.write("\n")
            if self.subproc.stderr is not None:
                for line in self.subproc.stderr:
                    log_message = line.decode("utf-8").strip()
                    self.loki_logger.log_text(log_message, io_type="std_err")
                    self.stderr.write(log_message)
                    self.stderr.flush()
                    self.stderr.write("\n")
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
