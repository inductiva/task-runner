"""File related utility functions."""
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import zipfile
import zlib
from typing import List, Optional

import stream_zip
from absl import logging

from task_runner import utils

DIR_NOT_FOUND_ERROR = "Directory does not exist."
PERMISSION_ERROR = "Insufficient permissions."
CMD_ERROR = "Error occurred during command."
CONVERT_INT_ERROR = "Output could not be converted to integer."
CMD_EMPTY_OUTPUT_ERROR = "Command output was empty."

DEFAULT_FILE_CHUNK_SIZE_BYTES = 65536  # 64 KiB
DEFAULT_ZIP_CHUNK_SIZE_BYTES = 65536  # 64 KiB
DEFAULT_ZIP_COMPRESS_LEVEL = 1


@utils.execution_time
def extract_zip_archive(zip_path: str, dest_dir: str) -> float:
    """Extract ZIP archive.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory where to write the uncompressed files.
    """
    with zipfile.ZipFile(zip_path, "r") as zip_fp:
        zip_fp.extractall(dest_dir)


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


def get_file_content_generator(file_path, chunk_size):
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


def get_dir_files_paths(directory):
    """Get all files and subdirectories from a directory."""
    paths = []

    def _update_paths(file_name, file_type):
        full_path = os.path.join(root, file_name)
        if os.path.islink(full_path):
            return

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


def get_zip_files(paths, chunk_size):
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
    now = utils.now_utc()

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
            stream_zip.ZIP_64,
            # Iterable of chunks of contents (empty for directories)
            get_file_content_generator(path.get("fs"), chunk_size)
            if path.get("type") == "file" else (),
        ) for path in paths)


def get_seven_zip_stream_process(
        local_path: str,
        bufsize: int = 4 * 1024 * 1024,  # 4 MB
) -> subprocess.Popen:
    """
    This function invokes the 7z command-line utility to compress files into a
    ZIP archive and returns a process object. The process will write to
    standard output and is configured with the specified buffer size.
    Use the process standard output as a stream.

    7z arguments used:
        a       : Add files to archive.
        -tzip   : Set the archive type to ZIP.
        -mx=1   : Set compression level to 1 (fastest).
        -mmt=on : Enable multithreading.
        -bso0   : Disable standard output messages.
        -bsp0   : Disable progress indicator on standard error.
        -so     : Write the archive to standard output.
        -an     : Disable archive name (used when outputting to stdout).
    """
    args = [
        "7zz", "a", "-tzip", "-mx=1", "-mmt=on", "-bso0", "-bsp0", "-so", "-an",
        "*"
    ]
    return subprocess.Popen(args,
                            bufsize,
                            cwd=local_path,
                            stdout=subprocess.PIPE)


def get_zip_generator(
    local_path: str,
    zip_chunk_size: int = DEFAULT_ZIP_CHUNK_SIZE_BYTES,
    compress_level: int = DEFAULT_ZIP_COMPRESS_LEVEL,
    files_chunk_size: int = DEFAULT_FILE_CHUNK_SIZE_BYTES,
) -> ChunkGenerator:
    """Get a generator for a ZIP archive.

    Args:
        local_path: Path to the directory to be zipped.
        zip_chunk_size: Size of the chunks of the zip file.
        compress_level: Compression level.
        files_chunk_size: Size of the chunks to read from the individual files.

    Advanced usage:
        https://stream-zip.docs.trade.gov.uk/advanced-usage/

    The level parameter for zlib.compressobj can be set from 0 to 9:
        - 0: No compression (fastest)
        - 1-3: Fast compression (less compression ratio)
        - 4-6: Balanced compression (moderate compression ratio and speed)
        - 7-9: High compression (better compression ratio but slower)

    Returns:
        Generator for a ZIP archive.
    """

    # Override the default compressobj which uses the
    # maximum compression level (9).
    def get_compressobj():
        return zlib.compressobj(
            wbits=-zlib.MAX_WBITS,
            level=compress_level,
        )

    paths = get_dir_files_paths(local_path)

    return ChunkGenerator(
        stream_zip.stream_zip(
            files=get_zip_files(paths, files_chunk_size),
            chunk_size=zip_chunk_size,
            get_compressobj=get_compressobj,
        ))


@utils.execution_time_with_result
def make_zip_archive(
    local_path: str,
    compress_level: int = DEFAULT_ZIP_COMPRESS_LEVEL,
) -> str:
    """
    Returns a zip of the local_path with compression level.

    Args:
        - local_path: str, path to the folder to compress
        - compress_level: int, compression level (0-9)

    Returns:
        - str: Path to the generated ZIP file
    """

    with tempfile.NamedTemporaryFile(suffix=".zip",
                                     delete=False) as temp_zip_file:
        output_zip = temp_zip_file.name

        with zipfile.ZipFile(output_zip,
                             "w",
                             zipfile.ZIP_DEFLATED,
                             compresslevel=compress_level) as zip_file:
            for foldername, _, filenames in os.walk(local_path):
                # Add directory (including empty folders) to the archive
                relative_folder_path = os.path.relpath(foldername, local_path)
                if relative_folder_path != ".":
                    zip_file.write(foldername,
                                   arcname=relative_folder_path + '/')

                # Add each file to the archive
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)

                    if os.path.islink(file_path):
                        continue

                    arcname = os.path.relpath(file_path, local_path)
                    zip_file.write(file_path, arcname=arcname)

    return output_zip


@utils.execution_time_with_result
def compress_with_seven_z(
    directory_name: str,
    compression_level: int = 1,
    archive_name: str = "archive.zip",
) -> str:
    zip_path = f"/tmp/{archive_name}"
    args = [
        "7zz", "a", "-tzip", f"-mx={compression_level}", "-mmt=on", zip_path,
        "*", "-bso0", "-bsp0"
    ]
    subprocess.run(args, cwd=directory_name, check=True)
    return zip_path


def extract_subfolder_and_cleanup(zip_path, subfolder, extract_to, workdir):
    """
    Extracts everything from the ZIP file, moves the files from the subfolder
    to the target location, and cleans up the rest.

    :param zip_path: Path to the ZIP file.
    :param subfolder: The name of the subfolder to extract.
    :param extract_to: The final directory to move the files to.
    :param workdir: The working directory
    """

    with tempfile.TemporaryDirectory(dir=workdir) as temp_dir:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        source_folder = os.path.join(temp_dir, subfolder)

        # Move the contents of the subfolder to the target location
        for item in os.listdir(source_folder):
            shutil.move(
                os.path.join(source_folder, item),
                os.path.join(extract_to, item),
            )

    # Remove the original ZIP file
    os.remove(zip_path)


def get_directory_filenames(directory_name: str) -> List[str]:
    return [
        os.path.join(path, filename)
        for path, _, filenames in os.walk(directory_name)
        for filename in filenames
    ]


def get_most_recent_timestamp(directory_name: str) -> Optional[float]:

    def _most_recent_timestamp(filename: str) -> float:
        stat = os.stat(filename)
        return max(stat.st_ctime_ns, stat.st_mtime_ns)

    filenames = get_directory_filenames(directory_name)
    return max(map(_most_recent_timestamp, filenames), default=None)


def get_last_modified_before_time(directory: str, reference_time_ns: float):
    """
    Get files in the specified directory that have a modification or
    creation time earlier than the given reference time.
    """
    directory = pathlib.Path(directory)
    if not directory.is_dir():
        raise ValueError(f"Not a directory: '{directory}'.")

    result = []
    for file in directory.iterdir():
        if file.is_dir():
            result.extend(get_last_modified_before_time(file,
                                                        reference_time_ns))
            continue

        if file.is_symlink() and not file.exists():
            result.append(file)
            continue

        file_stat = file.stat()
        if file_stat.st_mtime_ns > reference_time_ns or \
           file_stat.st_ctime_ns > reference_time_ns:
            continue

        result.append(file)

    return result
