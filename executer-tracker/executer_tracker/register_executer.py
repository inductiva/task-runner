"""Module for registering an executer with the API."""
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

import requests
from absl import logging

from executer_tracker.utils import gcloud, host

REGISTER_EXECUTER_ENDPOINT = "/executer-tracker/register"


def _get_executer_info() -> Dict:
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

    if gcloud.is_running_on_gcloud_vm():
        vm_info = gcloud.get_vm_info()
        if not vm_info:
            raise RuntimeError("Failed to get VM info.")

        executer_tracker_info["vm_name"] = vm_info.name
        executer_tracker_info["vm_id"] = vm_info.id

        logging.info("Running on GCloud VM:")
        logging.info("\t> VM type: %s", vm_info.type)
        logging.info("\t> VM preemptible: %s", vm_info.preemptible)
    else:
        executer_tracker_info["vm_name"] = os.environ.get("VM_NAME", None)
        executer_tracker_info["vm_id"] = os.environ.get("VM_ID", None)

    return executer_tracker_info


@dataclass
class ExecuterAccessInfo:
    id: UUID
    redis_stream: str
    redis_consumer_group: str
    redis_consumer_name: str


def register_executer(
    api_url: str,
    machine_group_id: Optional[UUID],
    num_mpi_hosts: int,
    mpi_cluster: bool = False,
) -> ExecuterAccessInfo:
    """Registers an executer in the API.

    This function inspects the environment of the executer and makes a request
    to the API to register it with the right information. The function returns
    a unique ID for the executer in the scope of the API, that it should use,
    for instance, when logging events.
    """

    url = f"{api_url}{REGISTER_EXECUTER_ENDPOINT}"

    executer_info = _get_executer_info()
    if machine_group_id:
        executer_info["machine_group_id"] = str(machine_group_id)

    executer_info["mpi_cluster"] = mpi_cluster
    executer_info["num_mpi_hosts"] = num_mpi_hosts

    logging.info("Registering executer with the API...")
    r = requests.post(
        url=url,
        json=executer_info,
        timeout=5,
    )

    if r.status_code != 202:
        raise RuntimeError(f"Failed to register executer: {r.text}")

    data = r.json()
    executer_id = UUID(data["uuid"])

    logging.info("Executer registered successfully:")
    logging.info("\t> Executer ID: %s", executer_id)

    return ExecuterAccessInfo(
        id=executer_id,
        redis_stream=data["redis_stream"],
        redis_consumer_group=data["redis_consumer_group"],
        redis_consumer_name=data["redis_consumer_name"],
    )
