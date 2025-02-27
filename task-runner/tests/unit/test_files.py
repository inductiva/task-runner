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
            with open(file_path, 'w') as f:
                f.write(random_string())

    temporary_directory = tempfile.TemporaryDirectory(delete=False)

    create_random_files(temporary_directory.name, 3)
    
    subdir_name = random_string()
    subdir_path = os.path.join(temporary_directory.name, subdir_name)
    os.makedirs(subdir_path)

    create_random_files(subdir_path, 2)

    yield temporary_directory
    temporary_directory.cleanup()


def test_remove_before_time_without_file_changes(directory):
    start_time = time.time()
    removed = files.remove_before_time(directory=directory.name,
                                       reference_time=start_time)
    assert len(removed) == 5


def test_remove_before_time_with_file_changes(directory):
    start_time = time.time()

    filenames = [
        os.path.join(path, filename)
        for path, _, filenames in os.walk(directory.name)
        for filename in filenames
    ]
    modified_files = [filenames[0], filenames[-1]]
    for modified_file in modified_files:
        with open(modified_file, "a") as file:
            file.write("\n")
    
    created_file = os.path.join(os.path.dirname(modified_files[0]), "new.txt")
    with open(created_file, "w") as file:
        file.write("\n")
    
    removed = files.remove_before_time(directory=directory.name,
                                       reference_time=start_time)
    assert len(removed) == 3

    filenames = [
        os.path.join(path, filename)
        for path, _, filenames in os.walk(directory.name)
        for filename in filenames
    ]

    assert created_file in filenames
    assert modified_files[0] in filenames
    assert modified_files[1] in filenames

