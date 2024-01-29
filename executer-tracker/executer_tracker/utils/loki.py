"""Logger for Loki server."""
from time import time_ns
import json
import requests
import os

from absl import logging


class LokiLogger:
    """Logger for Loki server."""

    def __init__(self, task_id):
        self.task_id = task_id
        self.server_url = (f"http://{os.getenv('LOGGING_HOSTNAME', 'loki')}"
                           ":3100/loki/api/v1/push")

    def log_text(self,
                 log_message,
                 timestamp=None,
                 io_type="",
                 project_id="0000-0000-0000-0000"):
        if timestamp is None:
            timestamp = self._get_current_timestamp()

        log_entry = {
            "streams": [{
                "stream": {
                    "task_id": self.task_id,
                    "io_type": io_type,
                    "project_id": project_id
                },
                "values": [[timestamp, log_message]],
            }]
        }

        response = requests.post(
            self.server_url,
            data=json.dumps(log_entry),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code != 204:
            logging.error(
                "Failed to send log entry. Status code: %s, Response: %s",
                response.status_code,
                response.text,
            )

    def _get_current_timestamp(self):
        # Get the current time in nanoseconds since the epoch
        return str(time_ns())
