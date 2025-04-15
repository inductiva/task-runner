import csv
import datetime
import enum
import os
from typing import List, Literal, Optional, Tuple
from uuid import UUID

import psutil
from absl import logging
from inductiva_api import events

from task_runner import BaseEventLogger, utils


class SystemMetrics(enum.Enum):
    CPU_USAGE = "cpu-usage"
    MEMORY_USAGE = "memory"
    DISK_INPUT = "disk-input"
    DISK_OUTPUT = "disk-output"


SYSTEM_METRICS_TO_FUNC = {
    SystemMetrics.CPU_USAGE: psutil.cpu_percent,
    SystemMetrics.MEMORY_USAGE: lambda: psutil.virtual_memory().percent,
    SystemMetrics.DISK_INPUT: lambda: psutil.disk_io_counters().read_bytes,
    SystemMetrics.DISK_OUTPUT: lambda: psutil.disk_io_counters().write_bytes
}


class SystemMonitor:

    METRICS_FILE_NAME = "system_metrics.csv"
    OUTPUT_MONITORING_FILE_NAME = "output_update.csv"

    def __init__(
        self,
        logs_dir: str,
        task_id: str,
        task_runner_uuid: UUID,
        event_logger: BaseEventLogger,
    ):
        self.logs_dir = logs_dir
        self.task_id = task_id
        self.task_runner_uuid = task_runner_uuid
        self.event_logger = event_logger
        self.command = None
        self.metrics = [metric for metric in SystemMetrics]

        self.metrics_file_path = os.path.join(logs_dir, self.METRICS_FILE_NAME)
        self.metrics_headers = ["time", "command"
                               ] + [metric.value for metric in self.metrics]
        self._create_log_file(self.metrics_file_path, self.metrics_headers)

        self.output_monitoring_file_path = os.path.join(
            logs_dir,
            self.OUTPUT_MONITORING_FILE_NAME,
        )

    def _write_csv(self, mode: Literal["a", "w"], file_path: str, row: List):
        with open(file_path, mode, encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def _create_log_file(self, file_path: str, headers: List):
        self._write_csv(mode="w", file_path=file_path, row=headers)

    def _log_row(self, file_path: str, row: List):
        self._write_csv(mode="a", file_path=file_path, row=row)

    def _get_last_data_row(self, file_path: str) -> Optional[List]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) < 1:
                    return None
                return rows[-1]
        except Exception as e:  # noqa: BLE001
            logging.error(f"An error occurred: {e}")
            return None

    def _get_last_modified_file(self) -> Tuple[Optional[float], Optional[str]]:
        last_epoch_timestamp = 0
        most_recent_file_epoch_timestamp = 0
        most_recent_file = None

        last_row = self._get_last_data_row(self.output_monitoring_file_path)

        if last_row:
            last_epoch_timestamp = datetime.datetime.fromisoformat(
                last_row[0]).timestamp()

        # Walk through the directory recursively
        for root, _, files in os.walk(self.logs_dir):
            for file in files:
                file_path = os.path.join(root, file)

                # Skip metrics log file
                if file_path == self.metrics_file_path:
                    continue

                # Get the timestamp of the file's last modification
                epoch_timestamp = os.path.getmtime(file_path)

                # Check if this file is the most recently modified
                if epoch_timestamp > most_recent_file_epoch_timestamp:
                    most_recent_file = file_path
                    most_recent_file_epoch_timestamp = epoch_timestamp

        if most_recent_file_epoch_timestamp <= last_epoch_timestamp:
            return None, None

        return most_recent_file_epoch_timestamp, most_recent_file

    def change_command(self, command):
        self.command = command

    def log_metrics(self):
        row = [utils.now_utc().isoformat(), self.command
              ] + [SYSTEM_METRICS_TO_FUNC[metric]() for metric in self.metrics]
        self._log_row(file_path=self.metrics_file_path, row=row)

    def monitor_output(self):
        epoch_timestamp, file_path = self._get_last_modified_file()

        if epoch_timestamp is not None:
            timestamp = datetime.datetime.fromtimestamp(
                epoch_timestamp,
                tz=datetime.timezone.utc,
            )

            # Always overwrite CSV without headers
            self._write_csv(
                mode="w",
                file_path=self.output_monitoring_file_path,
                row=[timestamp.isoformat(), file_path],
            )

            # Post event when output is stalled for more than 30 minutes
            if timestamp > utils.now_utc() - datetime.timedelta(seconds=1):
                self.event_logger.log(
                    events.TaskOutputStalled(
                        id=self.task_id,
                        machine_id=self.task_runner_uuid,
                    ))
