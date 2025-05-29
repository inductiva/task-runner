import os
import random
import string
import tempfile
import time

import pytest
from task_runner.utils import files


@pytest.fixture(name="directory", scope="function")
def fixture_directory():

    def random_string():
        return ''.join(random.choices(string.ascii_letters, k=10))

    def create_random_files(subdir_path, num_files):
        for _ in range(num_files):
            file_name = random_string() + '.txt'
            file_path = os.path.join(subdir_path, file_name)
            with open(file_path, 'w', encoding="utf-8") as f:
                f.write(random_string())

    temporary_directory = tempfile.TemporaryDirectory()

    create_random_files(temporary_directory.name, 3)

    subdir_name = random_string()
    subdir_path = os.path.join(temporary_directory.name, subdir_name)
    os.makedirs(subdir_path)

    create_random_files(subdir_path, 2)

    yield temporary_directory
    temporary_directory.cleanup()


@pytest.fixture(name="directory_with_symlinks", scope="function")
def fixture_directory_with_symlinks(directory):

    def make_symlinks(dirname):
        for filename in os.listdir(dirname):
            file_path = os.path.join(dirname, filename)
            symlink_path = os.path.join(dirname, f"symlink-{filename}")
            if os.path.isfile(file_path):
                os.symlink(file_path, symlink_path)
            elif os.path.isdir(file_path):
                make_symlinks(file_path)

    make_symlinks(dirname=directory.name)
    yield directory


@pytest.mark.parametrize("fixture_name",
                         ["directory", "directory_with_symlinks"])
def test_remove_before_time_without_file_changes(request, fixture_name):
    """
    Test that all files in the directory are removed when no files are
    modified or created after the reference time.
    """
    directory = request.getfixturevalue(fixture_name)
    timestamp = files.get_most_recent_timestamp(directory.name)
    before = files.get_directory_filenames(directory_name=directory.name)
    removed = files.get_last_modified_before_time(directory=directory.name,
                                                  reference_time_ns=timestamp)
    assert len(removed) == len(before)


def test_remove_before_time_with_file_changes(directory):
    """
    Test that only files created or modified after the reference time remain in
    the directory.
    """
    timestamp = files.get_most_recent_timestamp(directory.name)

    filenames = files.get_directory_filenames(directory_name=directory.name)

    # Assume simulation takes at least 1 milisecond
    time.sleep(0.001)

    modified_files = [filenames[0], filenames[-1]]
    for modified_file in modified_files:
        with open(modified_file, "a", encoding="utf-8") as file:
            file.write("\n")
            file.flush()

    created_file = os.path.join(os.path.dirname(modified_files[0]), "new.txt")
    with open(created_file, "w", encoding="utf-8") as file:
        file.write("\n")
        file.flush()

    removed = files.get_last_modified_before_time(directory=directory.name,
                                                  reference_time_ns=timestamp)
    assert len(removed) == 3

    filenames = files.get_directory_filenames(directory_name=directory.name)

    assert created_file in filenames
    assert modified_files[0] in filenames
    assert modified_files[1] in filenames
