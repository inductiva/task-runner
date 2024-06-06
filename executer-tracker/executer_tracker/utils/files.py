"""File related utility functions"""
import os
import shutil
import subprocess
import zipfile
from typing import Optional

import fsspec
from absl import logging

from executer_tracker.utils import execution_time

DIR_NOT_FOUND_ERROR = "Directory does not exist."
PERMISSION_ERROR = "Insufficient permissions."
CMD_ERROR = "Error occurred during command."
CONVERT_INT_ERROR = "Output could not be converted to integer."
CMD_EMPTY_OUTPUT_ERROR = "Command output was empty."


@execution_time
def make_zip_archive(zip_path: str, source_dir: str) -> float:
    # make_archive expects the path without extension
    zip_path_no_ext = os.path.splitext(zip_path)[0]
    zip_path = shutil.make_archive(zip_path_no_ext, "zip", source_dir)


@execution_time
def extract_zip_archive(zip_path: str, dest_dir: str) -> float:
    """Extract ZIP archive.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory where to write the uncompressed files.
    """
    with zipfile.ZipFile(zip_path, "r") as zip_fp:
        zip_fp.extractall(dest_dir)


@execution_time
def download_file(
    filesystem: fsspec.AbstractFileSystem,
    remote_path: str,
    local_path: str,
):
    with filesystem.open(remote_path, "rb") as f:
        with open(local_path, "wb") as local_file:
            shutil.copyfileobj(f, local_file)


@execution_time
def upload_file(
    filesystem: fsspec.AbstractFileSystem,
    local_path: str,
    remote_path: str,
):
    with open(local_path, "rb") as f_src:
        with filesystem.open(remote_path, "wb") as f_dest:
            shutil.copyfileobj(f_src, f_dest)


def get_dir_size(path: str) -> Optional[int]:
    try:
        total_size = subprocess.check_output(['du', '-sb',
                                              path]).split()[0].decode('utf-8')

        return int(total_size)

    except FileNotFoundError:
        logging.error(DIR_NOT_FOUND_ERROR)

    except PermissionError:
        logging.error(PERMISSION_ERROR)

    except subprocess.CalledProcessError:
        logging.error(CMD_ERROR)

    except ValueError:
        logging.error(CONVERT_INT_ERROR)

    except IndexError:
        logging.error(CMD_EMPTY_OUTPUT_ERROR)

    return None


def get_total_files_fast(path: str) -> int:
    total_files = int(
        subprocess.check_output(['find', path, '-type', 'f', '|', 'wc',
                                 '-l']).strip())
    return total_files


def get_dir_total_files(path: str) -> int:
    try:
        total_files = int(
            subprocess.check_output(f"find {path} -type f | wc -l",
                                    shell=True).strip())

        return total_files

    except FileNotFoundError:
        logging.error(DIR_NOT_FOUND_ERROR)

    except PermissionError:
        logging.error(PERMISSION_ERROR)

    except subprocess.CalledProcessError:
        logging.error(CMD_ERROR)

    except ValueError:
        logging.error(CONVERT_INT_ERROR)

    return None
