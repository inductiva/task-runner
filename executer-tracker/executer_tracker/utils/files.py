"""File related utility functions"""
import os
import shutil
import stat
import subprocess
import zipfile
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
CHUNK_SIZE_BYTES = 65536


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
    """Get all files and subdirectories from a directory."""
    paths = []

    def _update_paths(file_name, file_type):
        full_path = os.path.join(root, file_name)
        relative_path = os.path.relpath(full_path, directory)
        if file_type == "directory":
            relative_path += "/"
        paths.append({
            "fs": full_path,
            "name": relative_path,
            "type": file_type
        })

    for root, dirs, files in os.walk(directory):
        for file in files:
            _update_paths(file, "file")
        for dir in dirs:
            _update_paths(dir, "directory")

    return paths


def get_zip_files(paths):
    """Get member files for the ZIP archive generator.

    Basic usage:
    https://stream-zip.docs.trade.gov.uk/get-started/

    member_files = (
        (
            'my-file-1.txt',     # File name
            datetime.now(),      # Modification time
            S_IFREG | 0o600,     # Mode - regular file that owner can read and
                                 # write
            ZIP_32,              # ZIP_32 has good support but limited to 4GiB
            (b'Some bytes 1',),  # Iterable of chunks of contents
        ),
        (
            'my-file-2.txt',
            datetime.now(),
            S_IFREG | 0o600,
            ZIP_32,
            (b'Some bytes 2',),
        ),
    )

    ZIP_64 is used to support larger files (> 4 GiB):
    https://stream-zip.docs.trade.gov.uk/

    Input examples:
    https://stream-zip.docs.trade.gov.uk/input-examples/
    """
    now = now_utc()

    def contents(name):
        with open(name, "rb") as f:
            while chunk := f.read(CHUNK_SIZE_BYTES):
                yield chunk

    permissions = {
        # Read, write and execute permissions for the owner
        "directory": stat.S_IFDIR | 0o700,
        # Read and write permissions for the owner
        "file": stat.S_IFREG | 0o600,
    }

    return (
        (
            # File name
            path.get("name"),
            # Modification time
            now,
            # Mode
            permissions.get(path.get("type")),
            # ZIP_64 has good support for large files
            ZIP_64,
            # Iterable of chunks of contents (empty for directories)
            contents(path.get("fs")) if path.get("type") == "file" else (),
        ) for path in paths)


def get_zip_generator(local_path: str):
    """Get a generator for a ZIP archive."""
    paths = get_dir_files_paths(local_path)
    return ChunkGenerator(stream_zip(get_zip_files(paths)))
