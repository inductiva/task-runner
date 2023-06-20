"""Utility functions and constants.

This file defines miscelaneous utilities.
The submodule `files` contains utilities related to file handling.

NOTE: this file/module contains code that is present, similarly,
in the Web API codebase.
"""

INPUT_JSON_FILENAME = "input.json"
INPUT_ZIP_FILENAME = "input.zip"
OUTPUT_ZIP_FILENAME = "output.zip"
OUTPUT_DIR = "output"


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
