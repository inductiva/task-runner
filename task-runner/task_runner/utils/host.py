"""Utilities to get information about the host machine the task-runner is on."""
from dataclasses import dataclass

import psutil
import torch


@dataclass
class CPUCount:
    logical: int
    physical: int

@dataclass
class GPUCount:
    count: int
    name: int


def get_total_memory() -> int:
    """Get the total amount of virtual memory in bytes."""
    return psutil.virtual_memory().total


def get_cpu_count() -> CPUCount:
    """Get the number of logical and physical CPUs.

    Current limitations: this function gets the the total amount of cpus
    in the host machine. Since this is deployed in Docker containers that
    make use of cgroups to control the amount of cpus available to the
    container, this may not match the actual available resources to the
    container. For instance, if the host machine has 8 cpus and the container
    is limited to 4 cpus (with the --cpus flags), this function will still
    return 8 cpus.
    """

    return CPUCount(
        logical=psutil.cpu_count(logical=True),
        physical=psutil.cpu_count(logical=False),
    )


def get_gpu_count() -> GPUCount:
    return GPUCount(
        count=torch.cuda.device_count(),
        name=torch.cuda.get_device_properties(0).name)
