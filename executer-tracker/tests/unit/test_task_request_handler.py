"""Test TaskRequestHandler class."""
import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from typing import List
from unittest import mock

import pytest
from executer_tracker import (
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

    def run_subprocess(self, cmd: executers.Command, working_dir: str = ""):
        with self._lock:
            if self.is_shutting_down.is_set():
                raise executers.base_executer.ExecuterKilledError()

        self.subprocess = executers.SubprocessTracker(
            args=cmd.args,
            working_dir=working_dir,
            stdout=mock.MagicMock(),
            stderr=mock.MagicMock(),
            stdin=mock.MagicMock(),
            loki_logger=mock.MagicMock(),
        )
        self.subprocess.run()
        exit_code = self.subprocess.wait()
        if exit_code != 0:
            raise executers.base_executer.ExecuterSubProcessError(
                f"Command {cmd} failed with exit code {exit_code}")


class MockMessageListener(task_message_listener.BaseTaskMessageListener):
    """MessageListener mock that doesn't receive messages."""

    def __init__(self):
        self._event = threading.Event()

    def receive(self, task_id: str):
        del task_id  # unused
        self._event.wait()
        return "done"

    def unblock(self, task_id: str):
        del task_id  # unused
        self._event.set()


def download_input_side_effect(commands: List[str]):
    """Get function to use as side_effect for file_manager.download_input."""

    task_request_payload = {
        "sim_dir": "sim_dir",
        "container_image": "unused",
        "commands": [{
            "cmd": command,
            "prompts": []
        } for command in commands]
    }

    def _side_effect(task_id, task_dir_remote, tmp_zip_path):
        del task_id, task_dir_remote  # unused

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(
                    os.path.join(tmp_dir, "input.json"),
                    "w",
                    encoding="utf-8",
            ) as f:
                json.dump(task_request_payload, f)

            os.makedirs(os.path.join(tmp_dir, "sim_dir"), exist_ok=True)

            if tmp_zip_path.endswith(".zip"):
                tmp_zip_path = tmp_zip_path[:-len(".zip")]

            shutil.make_archive(tmp_zip_path, "zip", tmp_dir)

    return _side_effect


@pytest.fixture(name="handler")
def fixture_task_request_handler(tmp_path):
    id_ = uuid.uuid4()
    workdir = tmp_path.joinpath("workdir")
    workdir.mkdir()

    apptainer_images_manager = mock.MagicMock()
    apptainer_images_manager.get.return_value = ("docker://alpine:latest", 0.0)

    event_logger = mock.MagicMock()

    handler = task_request_handler.TaskRequestHandler(
        executer_uuid=id_,
        workdir=str(workdir),
        mpi_config=executers.MPIConfiguration(),
        apptainer_images_manager=apptainer_images_manager,
        api_client=mock.MagicMock(),
        event_logger=event_logger,
        message_listener=MockMessageListener(),
        file_manager=mock.MagicMock(),
    )

    with mock.patch("executer_tracker.api_methods_config.get_executer"
                   ) as get_executer_mock:
        with mock.patch("executer_tracker.utils.files.get_dir_size"
                       ) as get_dir_size_mock:
            get_dir_size_mock.return_value = 0
            get_executer_mock.return_value = MockExecuter
            yield handler


def _setup_mock_task(
    commands: List[str],
    handler: task_request_handler.TaskRequestHandler,
    time_to_live_seconds: float,
):
    task_id = "umx0oyincuy41x3u7fyazcwjr"
    task_request = {
        "id": task_id,
        "project_id": uuid.uuid4(),
        "task_dir": task_id,
        "container_image": "docker://alpine:latest",  # unused in test
        "time_to_live_seconds": str(time_to_live_seconds),
        "method": "arbitrary.arbitrary.run_simulation",
    }

    handler.file_manager.download_input = mock.MagicMock(
        side_effect=download_input_side_effect(commands=commands))

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

    assert end - start == pytest.approx(time_to_live_seconds, abs=0.5)
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

    start = time.time()
    handler(task_request)
    end = time.time()

    assert end - start == pytest.approx(task_duration_seconds, abs=0.5)
    # Check if last published event includes status 'success'
    assert handler.event_logger.log.call_args_list[-1][0][
        0].new_status == 'success'
