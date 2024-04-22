"""Logger for Loki server."""
import gzip
import json
import os
import threading
import time
from enum import Enum

import requests
from absl import logging

STREAM_BUFFER_MAX_LENGTH = 10
FLUSH_PERIOD_IN_SECONDS = 0.5
END_OF_STREAM = "<<end_of_stream>>"


class IOTypes(Enum):
    """Enumeration of IO types for logging."""
    COMMAND = "command"
    STD_OUT = "std_out"
    STD_ERR = "std_err"


class LogStream:
    """Class for managing a stream of logs."""

    def __init__(self, io_type: IOTypes, buffer_max_length: int):
        self.io_type = io_type
        self.buffer = []
        self.buffer_max_length = buffer_max_length
        self.last_send_time = time.time()

    def is_buffer_full(self) -> bool:
        """Returns True if the buffer is full, False otherwise."""
        return len(self.buffer) >= self.buffer_max_length

    def is_flush_period_elapsed(self) -> bool:
        """Returns True if the flush period has elapsed since the last
        send, False otherwise."""
        return time.time() - self.last_send_time >= FLUSH_PERIOD_IN_SECONDS


class LokiLogger:
    """This class manages logging to a Loki server. It maintains a separate log
    stream for each type of IO.
    """

    def __init__(self, task_id: str, project_id: str = "0000-0000-0000-0000"):
        self._enabled = threading.Event()
        self.task_id = task_id
        self.project_id = project_id
        self.server_url = (f"http://{os.getenv('LOGGING_HOSTNAME', 'loki')}"
                           ":3100/loki/api/v1/push")
        self.source = "executer-tracker"
        self.streams_dict = {}

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
                        "io_type": str(stream.io_type),
                        "project_id": self.project_id,
                        "source": self.source
                    },
                    "values": stream.buffer,
                }]
            }

            response = requests.post(
                self.server_url,
                data=gzip.compress(json.dumps(log_entry).encode('utf-8')),
                headers={
                    "Content-Type": "application/json",
                    "Content-Encoding": "gzip",
                },
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

        except Exception as e:  # noqa: BLE001
            logging.error("Exception caught: %s", str(e))

    def _get_current_timestamp(self) -> str:
        """Returns the current time in nanoseconds since the epoch."""
        return str(time.time_ns())

    def enable(self) -> None:
        """Enables the logger."""
        self._enabled.set()

    def disable(self) -> None:
        """Disables the logger."""
        self._enabled.clear()

    def is_enabled(self) -> bool:
        """Returns True if the logger is enabled, False otherwise."""
        return self._enabled.is_set()

    def log_text(self,
                 log_message: str,
                 timestamp: str = None,
                 io_type: IOTypes = None) -> None:
        """Appends log messages to each stream buffer and triggers the push to
        Loki server if the buffer is full or if the flush period has elapsed."""
        if not self.is_enabled():
            return

        if not io_type:
            logging.error("Stream IO type not specified. Log not sent!")
            return

        if timestamp is None:
            timestamp = self._get_current_timestamp()

        if io_type not in self.streams_dict:
            buffer_max_size = 1 if io_type == IOTypes.COMMAND \
                else STREAM_BUFFER_MAX_LENGTH
            self.streams_dict[io_type] = LogStream(io_type, buffer_max_size)

        stream: LogStream = self.streams_dict.get(io_type)
        stream.buffer.append([timestamp, log_message])

        if stream.is_buffer_full() or stream.is_flush_period_elapsed():
            self._send_logs(stream)

    def flush(self, io_type: IOTypes) -> None:
        """Sends the log stream of the specified IO type to Loki server, 
        regarless of whether the buffer is full or not."""
        if not self.is_enabled():
            return

        stream: LogStream = self.streams_dict.get(io_type)
        if not stream:
            message = f"Stream {str(io_type)} not found. Nothing to flush."
            logging.error(message)
            return
        self._send_logs(stream)
