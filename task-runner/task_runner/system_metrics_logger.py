import csv
import datetime
import enum
import os
from typing import List, Optional

import psutil


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


class SystemMetricsLogger:

    def __init__(
        self,
        log_file_path: str,
        log_file_name: str = "system_metrics.csv",
        metrics: Optional[List[SystemMetrics]] = None,
    ):
        if not metrics:
            metrics = [metric for metric in SystemMetrics]

        self.metrics = metrics
        self.log_file = os.path.join(log_file_path, log_file_name)
        self._create_log_file()
        self.command = None

    def _create_log_file(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "command"] +
                            [metric.value for metric in self.metrics])

    def change_command(self, command):
        self.command = command

    def log(self):
        with open(self.log_file, "a", encoding="utf-8") as f:
            writer = csv.writer(f)
            row_prefix = [datetime.datetime.now(), self.command]
            metrics = [
                SYSTEM_METRICS_TO_FUNC[metric]() for metric in self.metrics
            ]
            writer.writerow(row_prefix + metrics)
