"""Module for registering a task-runner with the API."""
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from absl import logging

import task_runner
import task_runner.api_client
from task_runner.utils import host


import torch


def _get_task_runner_info(local_mode: bool) -> dict:
    cpu_count = host.get_cpu_count()
    gpu_count = host.get_gpu_count()
    memory = host.get_total_memory()

    task_runner_info = {
        "create_time": datetime.now(timezone.utc).isoformat(),
        "cpu_count_logical": cpu_count.logical,
        "cpu_count_physical": cpu_count.physical,
        "memory": memory,
    }

    logging.info("Host resources:")
    logging.info("\t> CPUs (logical): %s", cpu_count.logical)
    logging.info("\t> CPUs (physical): %s", cpu_count.physical)
    logging.info("\t> Memory: %s B", memory)
    logging.info("\t> GPUs: %s", gpu_count.count)
    for i in range(gpu_count.count):
        logging.info("\t> GPUs name: %s", torch.cuda.get_device_properties(i).name)

    default_host_name = "local-mode-name" if local_mode else None
    default_host_id = "local-mode-id" if local_mode else None

    host_name = os.environ.get("HOST_NAME", default_host_name)
    host_id = os.environ.get("HOST_ID", default_host_id)
    if host_name is None or host_id is None:
        raise RuntimeError(
            "HOST_NAME and HOST_ID must be set in the environment.")

    task_runner_info["host_name"] = host_name
    task_runner_info["host_id"] = host_id

    return task_runner_info


def register_task_runner(
    api_client: task_runner.ApiClient,
    machine_group_id: Optional[UUID],
    num_mpi_hosts: int,
    mpi_cluster: bool = False,
    local_mode: bool = False,
) -> task_runner.api_client.TaskRunnerAccessInfo:
    """Registers an task_runner in the API.

    This function inspects the environment of the task_runner and makes a request
    to the API to register it with the right information. The function returns
    a unique ID for the task_runner in the scope of the API, that it should use,
    for instance, when logging events.
    """

    task_runner_info = _get_task_runner_info(local_mode=local_mode)
    if machine_group_id:
        task_runner_info["machine_group_id"] = str(machine_group_id)

    task_runner_info["mpi_cluster"] = mpi_cluster
    task_runner_info["num_mpi_hosts"] = num_mpi_hosts

    logging.info("Registering Task Runner with the API...")
    access_info = api_client.register_task_runner(task_runner_info)
    logging.info("Registered with following info:")
    logging.info(" > Task Runner ID: %s", access_info.id)
    logging.info(" > machine group ID: %s", access_info.machine_group_id)

    return access_info
