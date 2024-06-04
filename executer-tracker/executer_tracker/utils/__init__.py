"""Utility functions and constants.

This file defines miscelaneous utilities.
The submodule `files` contains utilities related to file handling.

NOTE: this file/module contains code that is present, similarly,
in the Web API codebase.
"""

import datetime
import time
from functools import wraps

INPUT_JSON_FILENAME = "input.json"
INPUT_ZIP_FILENAME = "input.zip"
OUTPUT_ZIP_FILENAME = "output.zip"
OUTPUT_DIR = "output"

QUEUE_TIME_SECONDS = "queue_time_seconds"
COMPUTATION_SECONDS = "computation_seconds"
DOWNLOAD_INPUT = "input_download_seconds"
UNZIP_INPUT = "input_decompression_seconds"
DOWNLOAD_EXECUTER_IMAGE = "container_image_download_seconds"
ZIP_OUTPUT = "output_compression_seconds"
UPLOAD_OUTPUT = "output_upload_seconds"
INPUT_SIZE = "input_size_bytes"
OUTPUT_SIZE = "output_size_bytes"


def make_task_key(task_id: str, attribute: str) -> str:
    """Auxiliary function to generate a Redis key to acess a task attribute.

    Args:
        task_id: task id
        attribute: name of the task attribute we want to get

    Returns:
        String representing the key to Redis.
        Example: "task:8273891:status"
    """
    return f"task:{task_id}:{attribute}"


def bool_string_to_bool(s: str) -> bool:
    """Converts a string representing a boolean to a boolean.

    Possible values that convert to True are "t" and "true", in
    a case-insensitive way.
    """
    return s.lower() in ("t", "true")


def execution_time(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        func(*args, **kwargs)
        return time.time() - start

    return wrapper


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
