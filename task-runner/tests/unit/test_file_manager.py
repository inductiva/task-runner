from unittest.mock import patch

import pytest
import requests
from task_runner import WebApiFileManager, utils


def test_retry_upload_failure(monkeypatch):
    """
    Test that WebApiFileManager.retry_upload retries the upload on failure,
    logs an error on every retry attempt except the last one, and finally
    raises the original exception when all attempts fail.
    """
    task_id = "task-123"
    runner_uuid = "task-runner-123"
    error_message = "Network down"
    max_attempt_number = 5
    multiplier = 0  # no actual waiting for test speed

    # Mock the upload method to always raise a ConnectionError
    def mock_upload(method, url, data):
        raise requests.ConnectionError(error_message)

    monkeypatch.setattr(WebApiFileManager, "upload", mock_upload)

    # Mock the utility function that extracts the root cause message
    def mock_get_exception_root_cause_message(error):
        return str(error)

    monkeypatch.setattr(utils, "get_exception_root_cause_message",
                        mock_get_exception_root_cause_message)

    # Patch the logging.error method to capture log calls
    with patch("absl.logging.error") as mock_log:

        # Expect a ConnectionError to be raised after all retries fail
        with pytest.raises(requests.ConnectionError):
            WebApiFileManager.retry_upload(
                method="POST",
                url="http://fake-url",
                data={},
                task_id=task_id,
                task_runner_uuid=runner_uuid,
                max_attempt_number=max_attempt_number,
                multiplier=multiplier,
            )

        # Verify logging.error was called on each retry except the last attempt
        assert mock_log.call_count == max_attempt_number - 1

        # Check the content of each logged message
        logging_messages = [
            call.args[0] % call.args[1:] if len(call.args) > 1 else call.args[0]
            for call in mock_log.call_args_list
        ]
        fmt = "Output upload failed for task %s on runner %s (retry %s): %s\n"
        for attempt, logging_message in enumerate(logging_messages):
            expected = fmt % (task_id, runner_uuid, attempt + 1, error_message)
            assert logging_message.startswith(expected)
