"""This file provides an abstract class to implement concrete executers.

Check the `BaseExecuter` docstring for more information on the class and
its usage.
"""
from abc import ABC, abstractmethod
import json
import os
from collections import namedtuple
import subprocess
from absl import logging


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

    def __init__(self):
        """Performs initial setup of the executer.

        This method creates the directories to be used for storing files
        that are sent to the client.
        """
        self.working_dir = os.getcwd()
        self.output_dir = os.path.join(self.working_dir, self.OUTPUT_DIRNAME)
        self.artifacts_dir = os.path.join(self.output_dir,
                                          self.ARTIFACTS_DIRNAME)
        os.makedirs(self.artifacts_dir)
        logging.info("Created output directory: %s", self.output_dir)
        logging.info("Created artifacts directory: %s", self.artifacts_dir)

        self._create_output_json_file()

        self.return_value = None
        self.stdout_logs_path = os.path.join(self.artifacts_dir,
                                             self.STDOUT_LOGS_FILENAME)
        self.stderr_logs_path = os.path.join(self.artifacts_dir,
                                             self.STDERR_LOGS_FILENAME)

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

    def run_subprocess(self, cmd: str, **kwargs):
        """Wrapper to subprocess.run() that correctly handles logging to files.

        This method should be used by executers to execute subprocesses, since
        it logs the processes' stdout and stderr to files. Since an executer
        can call more than one subprocess, and in order to improve the
        readibility and transparency of each command's logs, the resulting
        "stdout.txt" and "stderr.txt" files have separators splitting the logs
        of each command.

        Args:
            cmd: String representing the command to run the subprocess.
            kwargs: Keyword arguments to be passed to subprocess.run().
        """
        with open(self.stdout_logs_path, "a", encoding="UTF-8") as stdout, \
            open(self.stderr_logs_path, "a", encoding="UTF-8") as stderr:

            stdout.write(f"# COMMAND: {cmd}\n\n")
            stderr.write(f"# COMMAND: {cmd}\n\n")
            stdout.flush()
            stderr.flush()

            subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=stdout,
                stderr=stderr,
                **kwargs,
            )

            stdout.write("\n -------\n")
            stderr.write("\n -------\n")

    def run(self):
        """Method used to run the executer."""
        self.load_input_configuration()
        self.pre_process()
        self.execute()
        self.post_process()
        self.pack_output()
