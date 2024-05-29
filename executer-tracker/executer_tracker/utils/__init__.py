"""Utility functions and constants.

This file defines miscelaneous utilities.
The submodule `files` contains utilities related to file handling.

NOTE: this file/module contains code that is present, similarly,
in the Web API codebase.
"""

import time
from functools import wraps

INPUT_JSON_FILENAME = "input.json"
INPUT_ZIP_FILENAME = "input.zip"
OUTPUT_ZIP_FILENAME = "output.zip"
OUTPUT_DIR = "output"

DOWNLOAD_EXECUTER_IMAGE = "download_executer_image"
DOWNLOAD_INPUT = "download_input"
UNZIP_INPUT = "unzip_input"
ZIP_OUTPUT = "zip_output"
UPLOAD_OUTPUT = "upload_output"


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
