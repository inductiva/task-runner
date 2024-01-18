from time import time_ns
import json
import requests
import os


class LokiLogger:

    def __init__(self, task_id):
        self.task_id = task_id
        self.server_url = (
            f"http://{os.getenv('LOGGING_HOSTNAME', 'loki')}:3100/loki/api/v1/push"
        )

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
        )

        if response.status_code != 204:
            print(
                f"Failed to send log entry. Status code: {response.status_code}, Response: {response.text}"
            )

    def _get_current_timestamp(self):
        # Get the current time in nanoseconds since the epoch
        return str(time_ns())
