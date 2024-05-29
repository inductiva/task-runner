"""File related utility functions"""
import os
import shutil
import tempfile
import time
import zipfile

import fsspec
from absl import logging


def calculate_duration(start_time: float) -> float:
    return time.time() - start_time


def make_zip_archive(zip_path: str, source_dir: str) -> float:
    # make_archive expects the path without extension
    zip_start = time.time()

    zip_path_no_ext = os.path.splitext(zip_path)[0]
    zip_path = shutil.make_archive(zip_path_no_ext, "zip", source_dir)

    duration = calculate_duration(zip_start)

    logging.info("Created zip archive: %s", zip_path)

    return duration


# TODO: review if type annotations are correct
def extract_zip_archive(zip_path: str, dest_dir: str) -> float:
    """Extract ZIP archive.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory where to write the uncompressed files.
    """
    unzip_start = time.time()

    with zipfile.ZipFile(zip_path, "r") as zip_fp:
        zip_fp.extractall(dest_dir)

    return calculate_duration(unzip_start)


def download_file(
    filesystem: fsspec.AbstractFileSystem,
    remote_path: str,
    local_path: str,
):
    download_start = time.time()

    with filesystem.open(remote_path, "rb") as f:
        with open(local_path, "wb") as local_file:
            shutil.copyfileobj(f, local_file)

    return calculate_duration(download_start)


def download_and_extract_zip_archive(
    filesystem: fsspec.AbstractFileSystem,
    remote_path: str,
    dest_dir: str,
):
    """Download and extract ZIP archive from fsspec filesystem.

    Args:
        filesystem: fsspec filesystem.
        remote_path: Path to the ZIP file on the filesystem.
        dest_dir: Directory where to write the uncompressed files.
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_zip_path = os.path.join(tmp_dir, "file.zip")

        download_duration = download_file(
            filesystem=filesystem,
            remote_path=remote_path,
            local_path=tmp_zip_path,
        )
        # TODO: push duration to API
        print(download_duration)

        logging.info("Downloaded zip to: %s", tmp_zip_path)

        unzip_duration = extract_zip_archive(
            zip_path=tmp_zip_path,
            dest_dir=dest_dir,
        )
        # TODO: push duration to API
        print(unzip_duration)

        logging.info("Extracted zip to: %s", dest_dir)


def upload_file(
    filesystem: fsspec.AbstractFileSystem,
    local_path: str,
    remote_path: str,
):
    upload_start = time.time()

    with open(local_path, "rb") as f_src:
        with filesystem.open(remote_path, "wb") as f_dest:
            shutil.copyfileobj(f_src, f_dest)

    return calculate_duration(upload_start)
