"""Test TaskRequestHandler class."""
import json
import os
import queue
import shutil
import tempfile
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Dict, Optional
from unittest import mock

import pytest
from inductiva_api import events
from task_runner import (
    apptainer_utils,
    executers,
    task_message_listener,
    task_request_handler,
)


class MockExecuter(
        executers.arbitrary_commands_executer.ArbitraryCommandsExecuter):
    """Mock executer to use in tests that runs commands without apptainer.

    This class overrides the run_subprocess of the ArbitraryCommandsExecuter,
    to run the command without using apptainer.
    """

    def run_subprocess(self,
                       cmd: executers.Command,
                       working_dir: str = "",
                       env: Optional[Dict[str, str]] = None):
        with self._lock:
            if self.is_shutting_down.is_set():
                raise executers.base_executer.ExecuterKilledError()

        with tempfile.TemporaryDirectory() as tmp_dir:
            self.subprocess = executers.SubprocessTracker(
                args=cmd.args,
                working_dir=tmp_dir,
                stdout=mock.MagicMock(),
                stderr=mock.MagicMock(),
                stdin=mock.MagicMock(),
            )
            self.subprocess.run()
            exit_code = self.subprocess.wait()
            if exit_code != 0:
                raise executers.base_executer.ExecuterSubProcessError(
                    f"Command {cmd} failed with exit code {exit_code}")


class MockMessageListener(task_message_listener.BaseTaskMessageListener):
    """MessageListener mock that doesn't receive messages."""

    def __init__(self):
        self._queue = queue.Queue()

    def send(self, message: str):
        self._queue.put(message)

    def receive(self, task_id: str):
        del task_id  # unused

        msg = self._queue.get()
        return msg

    def unblock(self, task_id: str):
        del task_id  # unused
        self.send("done")


def download_input_side_effect(
        unblock_download_input: Optional[threading.Event] = None):
    """Get function to use as side_effect for file_manager.download_input."""

    def _side_effect(task_id, task_dir_remote, tmp_zip_path):
        del task_id, task_dir_remote  # unused

        with tempfile.TemporaryDirectory() as tmp_dir:
            os.makedirs(os.path.join(tmp_dir, "sim_dir"), exist_ok=True)

            if tmp_zip_path.endswith(".zip"):
                tmp_zip_path = tmp_zip_path[:-len(".zip")]

            shutil.make_archive(tmp_zip_path, "zip", tmp_dir)

        if unblock_download_input is not None:
            unblock_download_input.wait()

    return _side_effect


@pytest.fixture(name="mock_message_listener")
def fixture_message_listener() -> Iterator[MockMessageListener]:
    mock_message_listener = MockMessageListener()
    yield mock_message_listener


@pytest.fixture(name="handler")
def fixture_task_request_handler(
    tmp_path,
    mock_message_listener,
) -> Iterator[task_request_handler.TaskRequestHandler]:
    id_ = uuid.uuid4()
    workdir = tmp_path.joinpath("workdir")
    workdir.mkdir()
    container_path = workdir.joinpath("container.sif")
    container_path.touch()

    apptainer_images_manager = mock.MagicMock()
    apptainer_images_manager.get.return_value = (
        container_path,
        0.0,
        apptainer_utils.ApptainerImageSource.LOCAL_FILESYSTEM,
        0,
    )

    event_logger = mock.MagicMock()

    handler = task_request_handler.TaskRequestHandler(
        task_runner_uuid=id_,
        workdir=str(workdir),
        mpi_config=executers.MPIClusterConfiguration(),
        apptainer_images_manager=apptainer_images_manager,
        api_client=mock.MagicMock(),
        event_logger=event_logger,
        message_listener=mock_message_listener,
        file_manager=mock.MagicMock(),
    )

    with mock.patch(
            "task_runner.api_methods_config.get_executer") as get_executer_mock:
        with mock.patch(
                "task_runner.utils.files.get_dir_size") as get_dir_size_mock:
            get_dir_size_mock.return_value = 0
            get_executer_mock.return_value = MockExecuter
            yield handler


def _setup_mock_task(
    commands: list[str],
    handler: task_request_handler.TaskRequestHandler,
    time_to_live_seconds: Optional[float] = None,
    unblock_download_input: Optional[threading.Event] = None,
):
    task_id = "umx0oyincuy41x3u7fyazcwjr"
    extra_params = json.dumps({
        "sim_dir": "sim_dir",
        "run_subprocess_dir": None,
        "container_image": "unused",
        "commands": [{
            "cmd": command,
            "prompts": []
        } for command in commands]
    })
    task_request = {
        "id": task_id,
        "project_id": uuid.uuid4(),
        "task_dir": task_id,
        "container_image": "docker://alpine:latest",  # unused in test
        "simulator": "arbitrary_commands",
        "extra_params": extra_params,
    }

    if time_to_live_seconds is not None:
        task_request["time_to_live_seconds"] = str(time_to_live_seconds)

    handler.file_manager.download_input = mock.MagicMock(
        side_effect=download_input_side_effect(
            unblock_download_input=unblock_download_input))

    handler.file_manager.upload_output = mock.MagicMock(return_value=(0, 0, 0))

    return task_request


def test_task_request_handler_ttl_exceeded(handler):

    # Mocking because implementation is currently not cross platform
    time_to_live_seconds = 1
    task_duration_seconds = 10

    # Mock _build_executer to return a MockExecuter
    task_request = _setup_mock_task(
        commands=[f"sleep {task_duration_seconds}"],
        handler=handler,
        time_to_live_seconds=time_to_live_seconds,
    )

    start = time.time()
    handler(task_request)
    end = time.time()

    assert end - start == pytest.approx(time_to_live_seconds, abs=2)
    # Check if last published event includes status 'ttl-exceeded'
    assert handler.event_logger.log.call_args_list[-1][0][
        0].new_status == 'ttl-exceeded'


def test_task_request_handler_ttl_not_exceeded(handler):

    # Mocking because implementation is currently not cross platform
    time_to_live_seconds = 10
    task_duration_seconds = 1

    # Mock _build_executer to return a MockExecuter
    task_request = _setup_mock_task(
        commands=[f"sleep {task_duration_seconds}"],
        handler=handler,
        time_to_live_seconds=time_to_live_seconds,
    )

    start = time.perf_counter()
    handler(task_request)
    end = time.perf_counter()

    assert end - start >= task_duration_seconds

    # Our subprocess runner polls the subprocess every second, so a 1 second
    # task can take slightly more than 2 seconds to complete.
    assert end - start < task_duration_seconds + 1.2

    # Check if last published event includes status 'success'
    assert handler.event_logger.log.call_args_list[-1][0][
        0].new_status == 'success'


def test_task_request_handler_kill_task_before_computation_started(
    handler,
    mock_message_listener,
):
    unblock_download_input = threading.Event()

    # Mock _build_executer to return a MockExecuter
    task_request = _setup_mock_task(
        commands=["sleep 10"],
        handler=handler,
        unblock_download_input=unblock_download_input,
    )
    thread = threading.Thread(target=handler, args=(task_request,))
    thread.start()

    assert len(handler.event_logger.log.call_args_list) == 0
    mock_message_listener.send("kill")

    # download_input step is blocked until this event is set
    unblock_download_input.set()

    thread.join()

    # Check only one event was published (Killed) after PickedUp
    assert len(handler.event_logger.log.call_args_list) == 1
    assert isinstance(handler.event_logger.log.call_args_list[-1][0][0],
                      events.TaskKilled)


def test_task_request_handler_kill_task_after_computation_started(
    handler,
    mock_message_listener,
):
    # Mock _build_executer to return a MockExecuter
    task_duration = 30

    task_request = _setup_mock_task(
        commands=[f"sleep {task_duration}"],
        handler=handler,
    )
    thread = threading.Thread(target=handler, args=(task_request,))
    thread.start()

    computation_started = False
    computation_started_timeout_s = 30
    computation_started_check_period = 1
    # Wait until computation started event is published
    while not computation_started and computation_started_timeout_s > 0:
        computation_started = len(
            handler.event_logger.log.call_args_list) > 0 and isinstance(
                handler.event_logger.log.call_args_list[-1][0][0],
                events.TaskWorkStarted,
            )
        time.sleep(computation_started_check_period)
        computation_started_timeout_s -= computation_started_check_period

    assert computation_started

    mock_message_listener.send("kill")

    thread.join()

    assert len(handler.event_logger.log.call_args_list) == 3
    last_event = handler.event_logger.log.call_args_list[-1][0][0]
    assert isinstance(last_event, events.TaskOutputUploaded)
    assert last_event.new_status == "killed"
