"""This file provides an abstract class to implement concrete executers.

Check the `BaseExecuter` docstring for more information on the class and
its usage.
"""
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, Optional, Dict

import psutil
from absl import logging

from task_runner import SystemMonitor, executers
from task_runner.executers import command, mpi_configuration


def periodic_thread(
    function: callable,
    period_seconds: float,
    finished_event: threading.Event,
):
    while not finished_event.is_set():
        function()
        time.sleep(period_seconds)


class ExecuterKilledError(Exception):
    """Exception raised when the executer is killed."""

    def __init__(self) -> None:
        super().__init__("Executer was killed")


class ExecuterSubProcessError(Exception):
    """Exception raised when a subprocess ends with non-zero exit code."""

    def __init__(self, exit_code) -> None:
        super().__init__(f"Subprocess ended with exit code: {exit_code}")
        self.exit_code = exit_code


class BaseExecuter(ABC):
    """Base class to implement concrete executers.

    The `execute` method is abstract and should and should be implemented by
    all executers. Check the docstring of the `execute` method for information
    about how to handle inputs and outputs of the executer.

    Besides implementing a custom `execute` method, executer implementations
    should use the `run_subprocess` method to run subprocesses. Also,
    `self.artifacts_dir` specifies the path in which to store files and
    `self.working_dir` the path in which the executer is running (useful to
    construct absolute paths from input filenames).
    """
    OUTPUT_DIRNAME = "output"
    ARTIFACTS_DIRNAME = "artifacts"
    STDOUT_LOGS_FILENAME = "stdout.txt"
    STDERR_LOGS_FILENAME = "stderr.txt"

    def __init__(
        self,
        working_dir: str,
        container_image: str,
        mpi_config: mpi_configuration.MPIClusterConfiguration,
        exec_command_logger: executers.ExecCommandLogger,
        extra_params: dict[str, Any],
        system_monitor: SystemMonitor,
    ):
        """Performs initial setup of the executer.

        This method creates the directories to be used for storing files
        that are sent to the client.
        """
        self.mpi_config = mpi_config
        self.container_image = container_image
        self.working_dir = working_dir
        self.output_dir = os.path.join(self.working_dir, self.OUTPUT_DIRNAME)
        self.artifacts_dir = os.path.join(self.output_dir,
                                          self.ARTIFACTS_DIRNAME)
        self.working_dir_container = "/workdir"
        self.artifacts_dir_container = os.path.join(self.working_dir_container,
                                                    self.OUTPUT_DIRNAME,
                                                    self.ARTIFACTS_DIRNAME)
        self.exec_command_logger = exec_command_logger
        self.system_monitor = system_monitor

        named_tuple_constructor = namedtuple("args", extra_params.keys())
        self.args = named_tuple_constructor(**extra_params)

        logging.info("Working directory: %s", self.working_dir)

        os.makedirs(self.artifacts_dir)
        logging.info("Created output directory: %s", self.output_dir)
        logging.info("Created artifacts directory: %s", self.artifacts_dir)

        self.system_monitor.setup_logs(self.artifacts_dir)

        self._lock = threading.Lock()
        self.is_shutting_down = threading.Event()

        self.system_metrics_thread = threading.Thread(
            target=periodic_thread,
            args=(self.system_monitor.log_metrics, 30, self.is_shutting_down),
            daemon=True,
        )

        self.output_monitoring_thread = threading.Thread(
            target=periodic_thread,
            args=(self.system_monitor.monitor_output, 60,
                  self.is_shutting_down),
            daemon=True,
        )

        self.commands_user = os.environ.get("COMMANDS_USER")

        self.return_value = None
        self.stdout_logs_path = os.path.join(self.artifacts_dir,
                                             self.STDOUT_LOGS_FILENAME)
        self.stderr_logs_path = os.path.join(self.artifacts_dir,
                                             self.STDERR_LOGS_FILENAME)

        self.on_gpu = os.getenv("ON_GPU",
                                "false").lower() in ("true", "t", "yes", "y", 1)

    @abstractmethod
    def execute(self):
        """Abstract method that should be implemented by each executer.

        Each concrete executer should implement this method with the custom
        logic of the executer. The inputs to the executer are available
        in the `args` property of the object (accessible via `self.args`).
        A method can be specified in the client with the following signature:
            run_simulation(sim_dir, input_filename)
        For that case, the arguments will be available with the same name in
        the args namedtuple, i.e., `self.args.sim_dir` and
        `self.args.input_filename`.
        Note that if the input is a directory, then the path relative to
        `self.working_dir`.

        For an executer of a simulator that doesn't have a concrete output but
        rather generates files to be sent to the client, the files should
        be placed in the directory with path `self.artifacts_dir`.
        """
        raise NotImplementedError

    def pre_process(self):
        """Abstract method for pre-processing implemented by each executer.

        Each concrete executer should implement this method with the custom
        logic of the required pre-processing.
        The goal is to execute complex pre-processing tasks in the server
        side, that may require new dependencies that we don't want the
        user to install.
        """
        return None

    def post_process(self):
        """Abstract method for post-processing implemented by each executer.

        Each concrete executer should implement this method with the custom
        logic of the required post-processing.
        The goal is to provide these files by default on `task.get_output()`
        on the client. The post-process reads from the `self.artifacts_dir`
        to generate the required files.
        """
        return None

    def run_subprocess(
        self,
        cmd: command.Command,
        working_dir: str = "",
        env: Optional[Dict[str, str]] = None,
    ):
        """Run a command as a subprocess.

        This method is used to run a command as a subprocess. It uses the
        SubprocessTracker class to run the subprocess and wait for it to
        finish.

        The command is run in the right Apptainer container, by prefixing
        the command with the right Apptainer instruction.

        The method is also used to log the stdout and stderr of the command
        to the files "stdout.txt" and "stderr.txt" in the artifacts directory.
        Since an executer can call more than one subprocess, and in order to
        improve the readibility and transparency of each command's logs, the
        resulting "stdout.txt" and "stderr.txt" files have separators
        splitting the logs of each command.

        The method also writes the command's prompts to a file and pipes it
        to the subprocess' stdin. This is useful for commands that require
        user input.

        Args:
            cmd: Object of the Command class, encapsulating the command to
                to run as a subprocess and user prompts if applicable.
            working_dir: Path to the working directory of the subprocess.
        """
        with self._lock:
            if self.is_shutting_down.is_set():
                raise ExecuterKilledError()

        env = env or {}

        self.system_monitor.change_command(" ".join(cmd.args))

        stdin_path = os.path.join(self.working_dir, "stdin.txt")
        stdin_contents = "".join([f"{prompt}\n" for prompt in cmd.prompts])

        with open(stdin_path, "w", encoding="UTF-8") as f:
            f.write(stdin_contents)
            logging.info("Wrote stdin contents to %s: %d bytes", stdin_path,
                         len(stdin_contents))

        with open(self.stdout_logs_path, "a", encoding="UTF-8") as stdout, \
            open(self.stderr_logs_path, "a", encoding="UTF-8") as stderr, \
                open(stdin_path, "r", encoding="UTF-8") as stdin:
            log_message = (f"# COMMAND: {cmd.args}\n"
                           f"# Working directory: {working_dir}\n")
            log_message += "\n"
            stdout.write(log_message)
            stderr.write(log_message)
            stdout.flush()
            stderr.flush()

            args = []
            if cmd.is_mpi:
                args = self.mpi_config.build_command_prefix(
                    command_config=cmd.mpi_config)

            # This is the directory that contains all the task related files
            task_working_dir_host = self.working_dir
            task_working_dir_container = self.working_dir_container

            # This is the directory where the command will be executed. It
            # can be a subdirectory of the task directory.
            process_working_dir_container = task_working_dir_container
            if working_dir:
                process_working_dir_container = os.path.join(
                    process_working_dir_container, working_dir)

            apptainer_args = [
                "apptainer",
                "exec",
                "--no-mount",
                "cwd",
                "--home",
                "/home/apptainer",
                "--bind",
                f"{task_working_dir_host}:{task_working_dir_container}",
                "--pwd",
                process_working_dir_container,
            ]
            if self.mpi_config.local_mode:
                apptainer_args.append("--writable-tmpfs")
            if cmd.is_mpi and not self.mpi_config.local_mode:
                apptainer_args.append("--sharens")
            if self.on_gpu:
                apptainer_args.append("--nv")
            apptainer_args.append(self.container_image)

            apptainer_command_args = [*args, *apptainer_args, *cmd.args]
            command_args = [*args, *cmd.args]

            self.subprocess = executers.SubprocessTracker(
                args=apptainer_command_args,
                working_dir=None,
                stdout=stdout,
                stderr=stderr,
                stdin=stdin,
                run_as_user=self.commands_user,
                env=env,
            )
            self.exec_command_logger.log_command_started(
                command=" ".join(command_args),
                container_command=" ".join(apptainer_command_args),
            )
            start = time.perf_counter()
            self.subprocess.run()
            exit_code = self.subprocess.wait()
            execution_time = time.perf_counter() - start

            stdout.write("\n -------\n")
            stderr.write("\n -------\n")

        self.exec_command_logger.log_command_finished(
            exit_code=exit_code,
            execution_time_seconds=execution_time,
        )

        if exit_code != 0:
            raise ExecuterSubProcessError(exit_code)

    def run(self):
        """Method used to run the executer."""
        exit_code = 0
        self.system_metrics_thread.start()
        self.output_monitoring_thread.start()
        try:
            self.pre_process()
            self.execute()
            self.post_process()
            with self._lock:
                self.is_shutting_down.set()
        except ExecuterSubProcessError as e:
            exit_code = e.exit_code
        except ExecuterKilledError:
            # The executer was killed, so we don't need to do anything;
            # the exception was raised to stop the execution.
            pass

        return exit_code

    def terminate(self) -> bool:
        """Terminates the executer.

        Returns:
            True if the executer was successfully terminated, False if it
            had been terminated before.
        """
        with self._lock:
            if self.is_shutting_down.is_set():
                logging.info("Executer was already terminated. Skipping...")
                return False

            logging.info("Terminating executer...")
            self.is_shutting_down.set()

        if self.subprocess is not None:
            self.subprocess.exit_gracefully()

        return True

    def count_vcpus(self, hwthread):
        """Will count the vcpus on the machine.
        If hwthread is True will count logical cores.
        """
        if self.mpi_config.hostfile_path is None:
            return psutil.cpu_count(logical=hwthread)

        with open(self.mpi_config.hostfile_path, "r", encoding="utf-8") as f:
            hosts = f.readlines()

        hosts = [host.strip() for host in hosts if host != "\n"]

        total_cores = 0
        core_per_host = True
        for host_line in hosts:
            segments = host_line.split()
            if len(segments) > 1:
                _, slots = segments
                host_cores = int(slots.split("=")[1])

                total_cores += host_cores
            else:
                core_per_host = False
                continue

        if core_per_host:
            return total_cores
        else:
            return psutil.cpu_count(logical=hwthread) * len(hosts)
