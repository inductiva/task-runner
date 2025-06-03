"""Module that defines the SubprocessTracker class."""
import os
import signal
import subprocess
import time
from typing import IO

from absl import logging

from task_runner.utils import threads as threads_utils


def log_stream(stream: IO[bytes], output: IO[str]) -> None:
    """
    Reads lines from a stream and logs them.

    This function continuously reads lines from the given stream, decodes
    them to strings, and writes the decoded log messages to the Task-Runner
    stdout.

    Args:
        stream (IO[bytes]): Input stream to read from (stdout or stderr
                            from a subprocess).
        output (IO[str]): Task-Runner stdout.
    """
    for line in stream:
        try:
            log_message = line.decode("utf-8")
        except UnicodeDecodeError as e:
            logging.exception("Exception while decoding log message: %s", e)
            log_message = line.decode("utf-8", errors="replace")
        finally:
            output.write(log_message)
            output.flush()


class SubprocessTracker:
    """Class used to launch and manage a subprocess."""

    spawn_time = None
    command_line = None
    subproc = None

    def __init__(
        self,
        args: list[str],
        working_dir,
        stdout,
        stderr,
        stdin,
        run_as_user=None,
    ):
        logging.info("Creating task tracker for \"%s\".", args)
        self.args = args
        self.working_dir = working_dir
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = stdin
        self.threads = []
        self.run_as_user = run_as_user

    def run(self):
        """This is the main loop, where we execute the command and wait."""
        logging.info("Spawning subprocess for \"%s\".", self.args)
        self.spawn_time = time.perf_counter()

        user_args = []
        if self.run_as_user is not None:
            user_args = [
                "sudo",
                "-u",
                self.run_as_user,
            ]

        args = [*user_args, *self.args]

        try:
            # pylint: disable=consider-using-with
            self.subproc = subprocess.Popen(
                args,
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
                    args=(self.subproc.stdout, self.stdout),
                )
                stdout_thread.start()
                self.threads.append(stdout_thread)

            if self.subproc.stderr is not None:
                stderr_thread = threads_utils.ExceptionThread(
                    target=log_stream,
                    args=(self.subproc.stderr, self.stderr),
                )
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
                        sigterm_timeout: float = 10,
                        sigkill_delay: float = 5):
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

        self._invoke_signal(signal.SIGTERM)

        start_time = time.time()
        while not self._should_exit_kill_loop(start_time, sigterm_timeout):
            # After sigkill_delay, if the process is still running
            # (didnt exit with SIGTERM), send SIGKILL to force termination
            if time.time() - start_time >= sigkill_delay:
                self._invoke_signal(signal.SIGKILL)

            time.sleep(check_interval)

        logging.info("Waiting for subprocess_tracker threads join.")
        for thread in self.threads:
            thread.join()
        logging.info("All threads joined.")

        return self.subproc.poll()

    def _should_exit_kill_loop(self, start_time: float, timeout: int) -> bool:
        """Check if the process has exited or the timeout has been reached."""
        has_process_exited = self.subproc.poll() is not None
        are_streams_closed = all(
            not thread.is_alive() for thread in self.threads)

        has_timeout_elapsed = time.time() - start_time >= timeout

        return (has_process_exited and
                are_streams_closed) or has_timeout_elapsed

    def _invoke_signal(self, sig: signal.Signals):
        """Send a signal to the subprocess."""

        try:
            process_group_id = os.getpgid(self.subproc.pid)
            command = f"kill -{sig.value} -{process_group_id}"
            if self.run_as_user:
                command = f"sudo -i -u {self.run_as_user} {command}"

            subprocess.run(command, check=True, shell=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                (f"Failed to send signal {sig} "
                 f"to process group {self.subproc.pid}")) from exc
