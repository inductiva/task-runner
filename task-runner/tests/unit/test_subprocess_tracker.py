"""Test the subprocess tracker."""
import threading
import time
from unittest import mock

import pytest
from task_runner import executers


@pytest.fixture(name="mock_output_files")
def mock_output_files_generator(tmp_path):
    """Fixture for mocked stdout and stderr files."""
    stdout_file = tmp_path / "stdout.txt"
    stderr_file = tmp_path / "stderr.txt"
    with open(stdout_file, "w+",
              encoding="utf-8") as stdout, open(stderr_file,
                                                "w+",
                                                encoding="utf-8") as stderr:
        yield stdout, stderr

    # Clean up the files
    stdout_file.unlink()
    stderr_file.unlink()


def test_subprocess_tracker_init(mock_output_files):
    """Test the initialization of SubprocessTracker."""
    # Mocking dependencies
    mock_stdout, mock_stderr = mock_output_files

    # Create an instance of SubprocessTracker
    tracker = executers.SubprocessTracker(args=["echo", "Hello"],
                                          working_dir=".",
                                          stdout=mock_stdout,
                                          stderr=mock_stderr,
                                          stdin=None)

    # Assertions to verify the initialization
    assert tracker.args == ["echo", "Hello"]
    assert tracker.working_dir == "."
    assert tracker.stdout == mock_stdout
    assert tracker.stderr == mock_stderr
    assert tracker.stdin is None
    assert tracker.spawn_time is None
    assert tracker.command_line is None
    assert tracker.subproc is None


def test_run(mock_output_files):
    """Test the run method of SubprocessTracker."""
    mock_args = ["echo", "Hello"]
    mock_stdout, mock_stderr = mock_output_files

    tracker = executers.SubprocessTracker(args=mock_args,
                                          working_dir=".",
                                          stdout=mock_stdout,
                                          stderr=mock_stderr,
                                          stdin=None)

    tracker.run()
    exit_code = tracker.wait()

    assert exit_code == 0, f"Process exited with code {exit_code}"

    mock_stdout.seek(0)
    output = mock_stdout.read()
    assert "Hello" in output, f"Expected output \"Hello\" but got \"{output}\""

    mock_stderr.seek(0)
    output = mock_stderr.read()
    assert output == "", f"Expected empty stderr but got \"{output}\""


def test_run_with_multiple_stdout_lines(mock_output_files):
    """Test the run method of SubprocessTracker with multiple stdout lines."""
    mock_args = ["bash", "-c", "echo Hello; echo World; echo !; echo ?; echo !"]
    mock_stdout, mock_stderr = mock_output_files

    tracker = executers.SubprocessTracker(args=mock_args,
                                          working_dir=".",
                                          stdout=mock_stdout,
                                          stderr=mock_stderr,
                                          stdin=None)

    tracker.run()
    exit_code = tracker.wait()

    assert exit_code == 0, f"Process exited with code {exit_code}"

    mock_stdout.seek(0)
    output = mock_stdout.read()
    expected_output = "Hello\nWorld\n!\n?\n!\n"
    assert output == expected_output, (
        f"Expected output \"{expected_output}\" but got \"{output}\"")

    mock_stderr.seek(0)
    output = mock_stderr.read()
    assert output == "", f"Expected empty stderr but got \"{output}\""


def test_exit_gracefully(mock_output_files):
    """Test the exit_gracefully method of SubprocessTracker."""
    mock_args = ["sleep", "10"]
    mock_stdout, mock_stderr = mock_output_files

    tracker = executers.SubprocessTracker(args=mock_args,
                                          working_dir=".",
                                          stdout=mock_stdout,
                                          stderr=mock_stderr,
                                          stdin=None)

    # Run the subprocess in a separate thread to avoid blocking
    run_thread = threading.Thread(target=tracker.run)
    run_thread.start()

    time.sleep(1)  # Give some time for the process to start

    exit_code = tracker.exit_gracefully()

    run_thread.join()

    assert exit_code < 0, ("Process should have been terminated (exit code < 0)"
                           f" but got exit code {exit_code}")


def test_exit_gracefully_ignore_sigterm(mock_output_files):
    """Test the exit_gracefully method of SubprocessTracker.
    
    This test is to ensure that the SIGTERM signal is ignored.
    """
    # Command to ignore SIGTERM and run an infinite loop
    mock_args = ["bash", "-c", "trap '' TERM; while true; do sleep 1; done"]
    mock_stdout, mock_stderr = mock_output_files

    tracker = executers.SubprocessTracker(args=mock_args,
                                          working_dir=".",
                                          stdout=mock_stdout,
                                          stderr=mock_stderr,
                                          stdin=None)

    # Run the subprocess in a separate thread to avoid blocking
    run_thread = threading.Thread(target=tracker.run)
    run_thread.start()

    # Wait for a short duration to ensure the subprocess has started
    time.sleep(1)

    # Terminating the subprocess with SIGTERM should not work
    exit_code = tracker.exit_gracefully()
    exit_code_sigkill = -9

    assert exit_code == exit_code_sigkill, (
        "Process should have been killed (exit code -9)"
        f" but got exit code {exit_code}")

    run_thread.join()
