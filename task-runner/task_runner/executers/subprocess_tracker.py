"""Module that defines the SubprocessTracker class."""
import os
import signal
import subprocess
import time
from typing import IO, List

from absl import logging

from task_runner.utils import loki
from task_runner.utils import threads as threads_utils


def log_stream(stream: IO[bytes], loki_logger: loki.LokiLogger, output: IO[str],
               io_type: str) -> None:
    """
    Reads lines from a stream and logs them.

    This function continuously reads lines from the given stream, decodes
    them to strings, and logs each line using the provided logger.
    It also writes the decoded log messages to the Executer Tracker stdout.

    Args:
        stream (IO[bytes]): Input stream to read from (stdout or stderr
                            from a subprocess).
        loki_logger (LokiLogger): Logger instance to use for logging the
                                  decoded messages.
        output (IO[str]): Executer Tracker stdout.
        io_type (str): The I/O type associated with the stream (e.g., stdout or
                       stderr) used by the logger for categorizing messages.
    """
    for line in stream:
        log_message = line.decode("utf-8")
        loki_logger.log_text(log_message, io_type=io_type)
        output.write(log_message)
        output.flush()
    loki_logger.flush(io_type)


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
        self.threads = []

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
                stdout_thread = threads_utils.ExceptionThread(
                    target=log_stream,
                    args=(self.subproc.stdout, self.loki_logger, self.stdout,
                          loki.IOTypes.STD_OUT))
                stdout_thread.start()
                self.threads.append(stdout_thread)

            if self.subproc.stderr is not None:
                stderr_thread = threads_utils.ExceptionThread(
                    target=log_stream,
                    args=(self.subproc.stderr, self.loki_logger, self.stderr,
                          loki.IOTypes.STD_ERR))
                stderr_thread.start()
                self.threads.append(stderr_thread)

            # pylint: enable=consider-using-with

        except Exception as exception:  # noqa: BLE001
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
                if periodic_callback is not None:
                    periodic_callback()

                for thread in self.threads:
                    if not thread.is_alive():
                        thread.join()
                        if thread.exception is not None:
                            raise thread.exception

                time.sleep(period_secs)

        except Exception as exception:  # noqa: BLE001
            logging.warning("Caught exception \"%s\". Exiting gracefully",
                            exception)
            self.exit_gracefully()
            raise exception

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
            sigterm_timeout (`float`): How long the process should be given
                                    to exit gracefully after SIGTERM.
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

        for thread in self.threads:
            thread.join()

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
