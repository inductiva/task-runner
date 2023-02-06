"""File related utility functions"""
import os
import zipfile
from . import INPUT_JSON_FILENAME


def write_input_json(working_dir, params) -> str:
    """Write input json to a file.

    Args:
        working_dir: Directory in which to store the JSON file.
        params: Input params to write to the JSON file.

    Returns:
        The path to the input json.
    """
    input_json_path = os.path.join(working_dir, INPUT_JSON_FILENAME)
    with open(input_json_path, "w", encoding="UTF-8") as fp:
        fp.write(params)
    return input_json_path


def extract_zip_archive(zip_path, dest):
    """Extract ZIP archive.

    Args:
        zip_path: Path to the ZIP file.
        dest: Directory where to write the uncompressed files.
    """
    with zipfile.ZipFile(zip_path, "r") as zip_fp:
        zip_fp.extractall(dest)
