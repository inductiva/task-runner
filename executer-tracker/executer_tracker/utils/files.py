"""File related utility functions"""
import os
import zipfile
import tempfile
import shutil
from absl import logging
from pyarrow import fs


def make_zip_archive(zip_path, source_dir):
    # make_archive expects the path without extension
    zip_path_no_ext = os.path.splitext(zip_path)[0]

    zip_path = shutil.make_archive(zip_path_no_ext, "zip", source_dir)

    logging.info("Created zip archive: %s", zip_path)

    return zip_path


def extract_zip_archive(zip_path, dest_dir):
    """Extract ZIP archive.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory where to write the uncompressed files.
    """
    with zipfile.ZipFile(zip_path, "r") as zip_fp:
        zip_fp.extractall(dest_dir)


def download_and_extract_zip_archive(filesystem: fs.FileSystem,
                                     remote_path: str, dest_dir: str):
    """Download and extract ZIP archive from PyArrow filesystem.

    Args:
        filesystem: PyArrow filesystem.
        remote_path: Path to the ZIP file on the filesystem.
        dest_dir: Directory where to write the uncompressed files.
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_zip_path = os.path.join(tmp_dir, "file.zip")

        # `f.download` expects `f` to allow random access, so we need to
        # use `open_input_file` instead of `open_input_stream`
        with filesystem.open_input_file(remote_path) as f:
            f.download(tmp_zip_path)

        logging.info("Downloaded zip to: %s", tmp_zip_path)

        extract_zip_archive(
            zip_path=tmp_zip_path,
            dest_dir=dest_dir,
        )

        logging.info("Extracted zip to: %s", dest_dir)


def upload_file(filesystem: fs.FileSystem, file_path, file_path_remote):
    with open(file_path, "rb") as f_src:
        with filesystem.open_output_stream(file_path_remote) as f_dest:
            f_dest.upload(f_src)
