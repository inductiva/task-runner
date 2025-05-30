"""Utility functions and constants.

This file defines miscelaneous utilities.
The submodule `files` contains utilities related to file handling.

NOTE: this file/module contains code that is present, similarly,
in the Web API codebase.
"""

import datetime
import subprocess
import time
from functools import wraps

from absl import logging

from task_runner.utils.retries import retry

INPUT_JSON_FILENAME = "input.json"
INPUT_ZIP_FILENAME = "input.zip"
OUTPUT_ZIP_FILENAME = "output.zip"
OUTPUT_DIR = "output"

# Metrics
QUEUE_TIME_SECONDS = "queue_time_seconds"
COMPUTATION_SECONDS = "computation_seconds"
DOWNLOAD_INPUT = "input_download_seconds"
UNZIP_INPUT = "input_decompression_seconds"
DOWNLOAD_EXECUTER_IMAGE = "container_image_download_seconds"
EXECUTER_IMAGE_SIZE = "container_image_size_bytes"
UPLOAD_OUTPUT = "output_upload_seconds"
INPUT_ZIPPED_SIZE = "input_zipped_size_bytes"
INPUT_SIZE = "input_size_bytes"
OUTPUT_SIZE = "output_size_bytes"
OUTPUT_ZIPPED_SIZE = "output_zipped_size_bytes"
OUTPUT_TOTAL_FILES = "output_total_files"
OUTPUT_COMPRESSION_SECONDS = "output_compression_seconds"


def bool_string_to_bool(s: str) -> bool:
    """Converts a string representing a boolean to a boolean.

    Possible values that convert to True are "t" and "true", in
    a case-insensitive way.
    """
    return s.lower() in ("t", "true")


def execution_time(func):
    """Decorator to measure the execution time of a function."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        func(*args, **kwargs)
        return time.time() - start

    return wrapper


def execution_time_with_result(func):
    """Decorator to measure the execution time of a function and return the
    original result as well."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start
        return result, elapsed_time

    return wrapper


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def get_exception_root_cause_message(exc: Exception) -> str:
    """Gets the root cause of an exception and returns its message."""
    root_cause = exc
    while root_cause.__cause__:
        root_cause = root_cause.__cause__

    return str(root_cause)


def check_out_of_memory_killer(pid: int):
    """Use grep to check if a process was killed by the OOM killer via syslog.

    Args:
        pid: The PID to check.

    Returns:
        bool: True if OOM kill log is found, False otherwise.
    """
    oom_message = ("task-runner@standard.service: "
                   "A process of this unit has been killed by the OOM killer")
    command = f"tail -n 1000 /var/log/syslog | tac | grep -m 1 '{oom_message}'"

    try:
        completed_process = subprocess.run(
            command,
            capture_output=True,
            shell=True,
            check=True,
        )

        output = completed_process.stdout.decode(encoding="UTF-8")
        if oom_message in output:
            return True
    except subprocess.CalledProcessError as e:
        # Exit code 1 means "no matches found" — not a real error
        if e.returncode == 1:
            return False
        else:
            stdout = e.stdout.decode(encoding="UTF-8")
            stderr = e.stderr.decode(encodign="UTF-8")
            logging.warning(
                "Error checking if process was killed by OOM process."
                "\nStdout: %s\nStderr: %s", stdout, stderr)

    return False
