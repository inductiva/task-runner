"""Logger for Loki server."""
import json
import os
import requests
import time

from absl import logging

STREAM_BUFFER_MAX_LENGTH = 10
FLUSH_PERIOD = 0.5  # seconds


class IOTypes:
    """Enumeration of IO types for logging."""
    COMMAND = "command"
    STD_OUT = "std_out"
    STD_ERR = "std_err"


class LogStream:
    """Class for managing a stream of logs."""

    def __init__(self, io_type: str, buffer_max_length: int):
        self.io_type = io_type
        self.buffer = []
        self.buffer_max_length = buffer_max_length
        self.last_send_time = time.time()


class LokiLogger:
    """This class manages logging to a Loki server. It maintains a separate log
    stream for each type of IO.
    """

    def __init__(self, task_id: str, project_id: str = "0000-0000-0000-0000"):
        self.task_id = task_id
        self.project_id = project_id
        self.server_url = (f"http://{os.getenv('LOGGING_HOSTNAME', 'loki')}"
                           ":3100/loki/api/v1/push")
        self.streams = {}

    def _send_logs(self, stream: LogStream) -> None:
        """Sends logs to loki through a POST request to push endpoint."""
        try:
            if not stream.buffer:
                logging.info("Nothing to send. Buffer is empty.")
                return

            log_entry = {
                "streams": [{
                    "stream": {
                        "task_id": self.task_id,
                        "io_type": stream.io_type,
                        "project_id": self.project_id
                    },
                    "values": stream.buffer,
                }]
            }

            response = requests.post(
                self.server_url,
                data=json.dumps(log_entry),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code != 204:
                logging.error(
                    "Failed to send log entry. "
                    "Status code: %s, Response: %s",
                    response.status_code,
                    response.text,
                )

            stream.buffer = []
            stream.last_send_time = time.time()

        except Exception as e:  # pylint: disable=broad-except
            logging.error("Exception caught: %s", str(e))

    def _get_current_timestamp(self) -> str:
        """Returns the current time in nanoseconds since the epoch."""
        return str(time.time_ns())

    def log_text(self,
                 log_message: str,
                 timestamp: str = None,
                 io_type: str = None) -> None:
        """Appends log messages to each stream buffer and triggers the push to
        Loki server if the buffer is full or if the flush period has elapsed."""
        if not io_type:
            logging.error("Stream IO type not specified. Log not sent!")
            return

        if timestamp is None:
            timestamp = self._get_current_timestamp()

        if io_type not in self.streams:
            buffer_max_size = 1 if io_type == IOTypes.COMMAND \
                else STREAM_BUFFER_MAX_LENGTH
            self.streams[io_type] = LogStream(io_type, buffer_max_size)

        stream = self.streams[io_type]
        stream.buffer.append([timestamp, log_message])

        if len(stream.buffer) >= stream.buffer_max_length or time.time(
        ) - stream.last_send_time >= FLUSH_PERIOD:
            self._send_logs(stream)

    def flush(self, io_type: str) -> None:
        """Flushes the log stream of the specified IO type to the Loki
        server."""
        stream = self.streams.get(io_type)
        if not stream:
            logging.error("Stream %s not found. Nothing to flush.", io_type)
            return
        self._send_logs(stream)
