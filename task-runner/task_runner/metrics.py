"""Prometheus metrics server for task-runner service."""
import logging
import os

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Task metrics
tasks_active = Gauge('tasks_active', 'Number of currently active tasks')
tasks_total = Counter('tasks_total', 'Total number of tasks', ['status'])
task_duration = Histogram('task_duration_seconds',
                          'Task execution duration in seconds')


def start_metrics_server(port=None):
    """Start a basic Prometheus metrics server exposing client metrics."""
    port = port or int(os.getenv('TASK_RUNNER_METRICS_PORT', '8000'))
    start_http_server(port)
    logging.info("Metrics server started on port %s", port)
