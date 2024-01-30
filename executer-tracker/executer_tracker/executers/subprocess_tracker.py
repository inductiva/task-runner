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
            logging.info("Started process with PID %d.", self.subproc.pid)
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

    def exit_gracefully(self,
                        check_interval: float = 0.1,
                        sigterm_timeout: float = 5,
                        sigkill_delay: float = 1):
        """Ensures we kill the subprocess after signals or exceptions.

        First, it sends a SIGTERM signal to request a graceful shutdown. 
        If the process does not exit within the specified `sigkill_delay`, 
        it then sends a SIGKILL signal to forcefully terminate the process.
        The method checks the process status at intervals by `check_interval` 
        and returns the process's exit code upon termination.

        Args:
            check_interval (`float`): Check interval to see 
                                    if the process has exited.
            sigterm_timeout (`float`): How long to wait before sending SIGKILL.
            sigkill_delay (`float`): How long to wait before sending SIGKILL.
        
        Returns:
            The exit code of the process.

        Raises:
            RuntimeError: If the subproc attribute is not a Popen object.

        """
        if not isinstance(self.subproc, subprocess.Popen):
            raise RuntimeError("subproc is not a subprocess.Popen object.")

        logging.info("Sending SIGTERM to PID %d", self.subproc.pid)

        self._invoke_signal(signal.SIGTERM)

        start_time = time.time()
        while not self._should_exit_kill_loop(start_time, sigterm_timeout):
            # After sigkill_delay, if the process is still running
            # (didnt exit with SIGTERM), send SIGKILL to force termination
            if time.time() - start_time >= sigkill_delay:
                logging.info("Sending SIGKILL to PID %d", self.subproc.pid)
                self._invoke_signal(signal.SIGKILL)

            time.sleep(check_interval)

        return self.subproc.poll()

    def _should_exit_kill_loop(self, start_time: float, timeout: int) -> bool:
        """Check if the process has exited or the timeout has been reached."""
        has_process_exited = self.subproc.poll() is not None
        has_timeout_elapsed = time.time() - start_time >= timeout
        return has_process_exited or has_timeout_elapsed

    def _invoke_signal(self, sig: signal.Signals):
        """Send a signal to the subprocess."""
        try:
            process_group_id = os.getpgid(self.subproc.pid)
            os.killpg(process_group_id, sig)
        except OSError as exc:
            raise RuntimeError(
                (f"Failed to send signal {sig} "
                 f"to process group {self.subproc.pid}")) from exc
