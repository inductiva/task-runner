"""Util functions related to executer-tracker config."""
import os
import uuid
from typing import Optional

from absl import logging


def get_machine_group_id() -> Optional[uuid.UUID]:
    """Get machine group ID from env variable or GCloud VM metadata.

    First checks if the MACHINE_GROUP_ID env variable is set. If not, tries to
    get the value from the GCloud VM metadata.

    Returns:
        Machine group UUID or None if not found.
    """

    machine_group_str = os.getenv("MACHINE_GROUP_ID")
    if machine_group_str is None:
        return

    logging.info("Machine group: %s", machine_group_str)

    if not machine_group_str:  # check if is None or empty string
        return None

    return uuid.UUID(machine_group_str)


def get_machine_group_name() -> Optional[str]:
    machine_group_name = os.getenv("MACHINE_GROUP_NAME")

    logging.info("Machine group: %s", machine_group_name)

    if not machine_group_name:  # check if is None or empty string
        return None

    return machine_group_name


def is_machine_group_local() -> bool:
    """Check if the machine group is local."""
    local_mode = os.getenv("LOCAL_MODE",
                           "true").lower() in ("true", "t", "yes", "y", 1)
    logging.info("Running in local mode: %s", local_mode)

    return local_mode
