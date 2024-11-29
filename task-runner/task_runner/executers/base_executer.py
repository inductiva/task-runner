"""This file provides an abstract class to implement concrete executers.

Check the `BaseExecuter` docstring for more information on the class and
its usage.
"""
import json
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import namedtuple

import psutil
from absl import logging

from task_runner import executers
from task_runner.executers import command, mpi_configuration
from task_runner.utils import loki


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

    The `load_input_configuration` and `pack_output` methods perform
    boilerplate code used in all executers. The `execute` method is abstract
    and should and should be implemented by all executers. Check the docstring
    of the `execute` method for information about how to handle inputs and
    outputs of the executer.

    Besides implementing a custom `execute` method, executer implementations
    should use the `run_subprocess` method to run subprocesses. Also,
    `self.artifacts_dir` specifies the path in which to store files and
    `self.working_dir` the path in which the executer is running (useful to
    construct absolute paths from input filenames).
    """
    INPUT_FILENAME = "input.json"
    OUTPUT_DIRNAME = "output"
    ARTIFACTS_DIRNAME = "artifacts"
    OUTPUT_FILENAME = "output.json"
    STDOUT_LOGS_FILENAME = "stdout.txt"
    STDERR_LOGS_FILENAME = "stderr.txt"

    def __init__(
        self,
        working_dir: str,
        container_image: str,
        mpi_config: mpi_configuration.MPIClusterConfiguration,
        loki_logger: loki.LokiLogger,
        exec_command_logger: executers.ExecCommandLogger,
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
        self.loki_logger = loki_logger
        self.exec_command_logger = exec_command_logger

        logging.info("Working directory: %s", self.working_dir)

        os.makedirs(self.artifacts_dir)
        logging.info("Created output directory: %s", self.output_dir)
        logging.info("Created artifacts directory: %s", self.artifacts_dir)

        self._create_output_json_file()

        self._lock = threading.Lock()
        self.is_shutting_down = threading.Event()

        self.return_value = None
        self.stdout_logs_path = os.path.join(self.artifacts_dir,
                                             self.STDOUT_LOGS_FILENAME)
        self.stderr_logs_path = os.path.join(self.artifacts_dir,
                                             self.STDERR_LOGS_FILENAME)

        self.on_gpu = os.getenv("ON_GPU",
                                "false").lower() in ("true", "t", "yes", "y", 1)

    def _create_output_json_file(self):
        self.output_json_path = os.path.join(self.output_dir,
                                             self.OUTPUT_FILENAME)

        with open(self.output_json_path, "w", encoding="UTF-8") as f:
            json.dump([], f)

    def load_input_configuration(self):
        """Method that loads the executers' inputs.

        This method reads the inputs from a json file and creates a named
        tuple (`self.args`) to be used in the execute method.
        """
        input_file_path = os.path.join(self.working_dir, self.INPUT_FILENAME)

        with open(input_file_path, "r", encoding="utf-8") as f:
            input_dict = json.load(f)

        named_tuple_constructor = namedtuple("args", input_dict.keys())
        self.args = named_tuple_constructor(**input_dict)

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

    def pack_output(self):
        """Method that packs the output to send for the client.

        This method assumes that the return value of the executer is stored
        in the object's `return_value` property.
        For simulators that don't have a specific output, but rather output
        a series of files, then `return_value` doesn't need to be set, as by
        default the contents of the `artifacts_dir` directory are considered to
        be the output.
        For other executers that return a specific value, the `return_value`
        must be set with the object expected in the client. For executers that
        return more than one value, e.g. eigen decomposition, which returns the
        eigenvalues and eigenvectors, then `return_value` must be a tuple with
        the two objects in the order expected in the client.
        """
        with open(self.output_json_path, "w", encoding="UTF-8") as f:
            if self.return_value is None:
                json_obj = []
            elif isinstance(self.return_value, tuple):
                json_obj = list(self.return_value)
            else:
                json_obj = [self.return_value]

            json.dump(json_obj, f)

    def close_streams(self):
        """Method that signals the end of log streams used by the executer."""
        for io_type in loki.IOTypes:
            self.loki_logger.log_text(loki.END_OF_STREAM, io_type=io_type)
            self.loki_logger.flush(io_type)

    def run_subprocess(
        self,
        cmd: command.Command,
        working_dir: str = "",
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

        stdin_path = os.path.join(self.working_dir, "stdin.txt")
        stdin_contents = "".join([f"{prompt}\n" for prompt in cmd.prompts])

        with open(stdin_path, "w", encoding="UTF-8") as f:
            f.write(stdin_contents)
            logging.info("Wrote stdin contents to %s: %d bytes", stdin_path,
                         len(stdin_contents))

        with open(self.stdout_logs_path, "a", encoding="UTF-8") as stdout, \
            open(self.stderr_logs_path, "a", encoding="UTF-8") as stderr, \
                open(stdin_path, "r", encoding="UTF-8") as stdin:
            log_message = f"# COMMAND: {cmd.args}\n"
            self.loki_logger.log_text(log_message, io_type=loki.IOTypes.COMMAND)
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
            task_working_dir = self.working_dir

            # This is the directory where the command will be executed. It
            # can be a subdirectory of the task directory.
            process_working_dir = task_working_dir
            if working_dir:
                process_working_dir = os.path.join(process_working_dir,
                                                   working_dir)
            apptainer_args = [
                "apptainer",
                "exec",
                "--bind",
                f"{task_working_dir}:{task_working_dir}",
                "--pwd",
                process_working_dir,
            ]
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
                loki_logger=self.loki_logger,
            )
            self.exec_command_logger.log_command_started(
                command=" ".join(command_args),
                container_command=" ".join(apptainer_command_args),
            )
            start = time.perf_counter()
            self.subprocess.run()
            exit_code = self.subprocess.wait()
            execution_time = time.perf_counter() - start

            self.exec_command_logger.log_command_finished(
                exit_code=exit_code,
                execution_time_seconds=execution_time,
            )

            if exit_code != 0:
                raise ExecuterSubProcessError(exit_code)

            stdout.write("\n -------\n")
            stderr.write("\n -------\n")

    def run(self):
        """Method used to run the executer."""
        exit_code = 0

        try:
            self.load_input_configuration()
            self.pre_process()
            self.execute()
            self.post_process()
            with self._lock:
                self.is_shutting_down.set()
            self.pack_output()
        except ExecuterSubProcessError as e:
            exit_code = e.exit_code
        except ExecuterKilledError:
            # The executer was killed, so we don't need to do anything;
            # the exception was raised to stop the execution.
            pass
        finally:
            self.close_streams()

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
