"""Module for registering an executer with the API."""
import os
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from absl import logging

import executer_tracker
import executer_tracker.api_client
from executer_tracker.utils import host


def _get_executer_info(local_mode: bool) -> Dict:
    cpu_count = host.get_cpu_count()
    memory = host.get_total_memory()

    executer_tracker_info = {
        "create_time": datetime.now(timezone.utc).isoformat(),
        "cpu_count_logical": cpu_count.logical,
        "cpu_count_physical": cpu_count.physical,
        "memory": memory,
    }

    logging.info("Executer resources:")
    logging.info("\t> CPUs (logical): %s", cpu_count.logical)
    logging.info("\t> CPUs (physical): %s", cpu_count.physical)
    logging.info("\t> Memory: %s B", memory)

    default_vm_name = "local-mode-name" if local_mode else None
    default_vm_id = "local-mode-id" if local_mode else None

    vm_name = os.environ.get("VM_NAME", default_vm_name)
    vm_id = os.environ.get("VM_ID", default_vm_id)
    if vm_name is None or vm_id is None:
        raise RuntimeError("VM_NAME and VM_ID must be set in the environment.")

    executer_tracker_info["vm_name"] = vm_name
    executer_tracker_info["vm_id"] = vm_id

    return executer_tracker_info


def register_executer(
    api_client: executer_tracker.ApiClient,
    machine_group_id: Optional[UUID],
    num_mpi_hosts: int,
    mpi_cluster: bool = False,
    local_mode: bool = False,
) -> executer_tracker.api_client.ExecuterAccessInfo:
    """Registers an executer in the API.

    This function inspects the environment of the executer and makes a request
    to the API to register it with the right information. The function returns
    a unique ID for the executer in the scope of the API, that it should use,
    for instance, when logging events.
    """

    executer_info = _get_executer_info(local_mode=local_mode)
    if machine_group_id:
        executer_info["machine_group_id"] = str(machine_group_id)

    executer_info["mpi_cluster"] = mpi_cluster
    executer_info["num_mpi_hosts"] = num_mpi_hosts

    logging.info("Registering executer-tracker with the API...")
    access_info = api_client.register_executer_tracker(executer_info)
    logging.info("Registered with following info:")
    logging.info(" > executer-tracker ID: %s", access_info.id)
    logging.info(" > machine group ID: %s", access_info.machine_group_id)

    return access_info
