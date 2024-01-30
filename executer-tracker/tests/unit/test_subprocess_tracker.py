"""Test the subprocess tracker."""
import pytest
import time
import threading
from unittest import mock
from executer_tracker import executers


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
    mock_loki_logger = mock.MagicMock()

    # Create an instance of SubprocessTracker
    tracker = executers.SubprocessTracker(args=["echo", "Hello"],
                                          working_dir=".",
                                          stdout=mock_stdout,
                                          stderr=mock_stderr,
                                          stdin=None,
                                          loki_logger=mock_loki_logger)

    # Assertions to verify the initialization
    assert tracker.args == ["echo", "Hello"]
    assert tracker.working_dir == "."
    assert tracker.stdout == mock_stdout
    assert tracker.stderr == mock_stderr
    assert tracker.stdin is None
    assert tracker.loki_logger == mock_loki_logger
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
                                          stdin=None,
                                          loki_logger=mock.MagicMock())

    tracker.run()

    mock_stdout.seek(0)
    output = mock_stdout.read()
    assert "Hello" in output

    mock_stderr.seek(0)
    output = mock_stderr.read()
    assert output == ""


def test_exit_gracefully(mock_output_files):
    """Test the exit_gracefully method of SubprocessTracker."""
    mock_args = ["sleep", "10"]
    mock_stdout, mock_stderr = mock_output_files

    tracker = executers.SubprocessTracker(args=mock_args,
                                          working_dir=".",
                                          stdout=mock_stdout,
                                          stderr=mock_stderr,
                                          stdin=None,
                                          loki_logger=mock.MagicMock())

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
                                          stdin=None,
                                          loki_logger=mock.MagicMock())

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
