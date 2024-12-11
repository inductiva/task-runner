import enum
import os

import host


class SystemMetrics(enum.Enum):
    CPU_COUNT_LOGICAL = "cpu_count_logical"
    CPU_COUNT_PHYSICAL = "cpu_count_physical"
    MEMORY = "memory"
    HOST_NAME = "host_name"
    HOST_ID = "host_id"


SYSTEM_METRICS_TO_FUNC = {
    SystemMetrics.CPU_COUNT_LOGICAL: host.get_cpu_count().logical,
    SystemMetrics.CPU_COUNT_PHYSICAL: host.get_cpu_count().physical,
    SystemMetrics.MEMORY: host.get_total_memory(),
    SystemMetrics.HOST_NAME: os.environ.get("HOST_NAME", "local-mode-name"),
    SystemMetrics.HOST_ID: os.environ.get("HOST_ID", "local-mode-id"),
}


class SystemMetricsLogger:

    def __init__(self):
        self.metrics = []

    def add_metric(self, metric):
        self.metrics.append(metric)

    def _log():
        pass
