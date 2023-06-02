from dataclasses import dataclass
import subprocess
from typing import Optional
from absl import logging
import psutil
import uuid


def get_cpu_info_verbose() -> Optional[str]:
    """Get verbose CPU information in unstructured text format.

    This fails if the "lscpu" binary is not available.
    """
    try:
        cpu_info = subprocess.check_output("lscpu").decode("utf-8")
    except FileNotFoundError:
        logging.warn(
            "\"lscpu\" binary not found. Verbose CPU info not available.")
        return None

    return cpu_info


@dataclass
class CPUCount:
    logical: int
    physical: int


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
