"""File related utility functions"""
import os
import shutil
import subprocess
import zipfile
from stat import S_IFREG
from typing import Optional

import fsspec
from absl import logging
from stream_zip import ZIP_64, stream_zip

from executer_tracker.utils import execution_time, now_utc

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


class ChunkGenerator:

    def __init__(self, iterator):
        self.iterator = iterator
        self.total_bytes = 0

    def __iter__(self):
        return self

    def __next__(self):
        chunk = next(self.iterator)
        self.total_bytes += len(chunk)
        return chunk


def get_dir_files_paths(directory):
    """Get all files from a directory."""
    paths = []

    for root, _, files in os.walk(directory):
        for file in files:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, directory)
            paths.append({"fs": full_path, "name": relative_path})

    return paths


def get_zip_files(paths):
    """Get member files for the ZIP archive generator.

    ZIP_64 is used to support larger files (> 4 GiB):
    https://stream-zip.docs.trade.gov.uk/

    Input examples:
    https://stream-zip.docs.trade.gov.uk/input-examples/
    """
    now = now_utc()

    def contents(name):
        with open(name, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return ((path.get("name"), now, S_IFREG | 0o600, ZIP_64,
             contents(path.get("fs"))) for path in paths)


def get_zip_generator(local_path: str):
    """Get a generator for a ZIP archive."""
    paths = get_dir_files_paths(local_path)
    return ChunkGenerator(stream_zip(get_zip_files(paths)))
