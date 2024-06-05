"""File related utility functions"""
import os
import shutil
import zipfile

import fsspec

from executer_tracker.utils import execution_time


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
