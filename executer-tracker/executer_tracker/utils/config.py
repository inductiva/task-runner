"""Util functions related to executer-tracker config."""
import dataclasses
import json
import os
import uuid
from typing import Dict, Optional

from absl import logging

from executer_tracker.utils import gcloud


def get_machine_group_id() -> Optional[uuid.UUID]:
    """Get machine group ID from env variable or GCloud VM metadata.

    First checks if the MACHINE_GROUP_ID env variable is set. If not, tries to
    get the value from the GCloud VM metadata.

    Returns:
        Machine group UUID or None if not found.
    """

    machine_group_str = os.getenv("MACHINE_GROUP_ID")
    if machine_group_str is None:
        machine_group_str = gcloud.get_vm_metadata_value(
            "attributes/machine_group")

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


@dataclasses.dataclass
class ExecuterConfig:
    image: str


def load_executers_config() -> Dict[str, ExecuterConfig]:
    """Load supported executer types from config file.

    This is a mapping of executer types to their respective Docker image names.
    The Docker image names are used to fetch Apptainer images from the
    Apptainer image storage.
    It should be a JSON file with the following format:
        {
            "gromacs": {
                "image": "inductiva/kutu:gromacs_2022.2_dev"
            },
            "openfoam-foundation": {
                "image": "inductiva/kutu:openfoam-foundation_v8_dev"
            }
        }
    """

    config_path = os.getenv("EXECUTERS_CONFIG")
    if not config_path:
        raise ValueError("EXECUTERS_CONFIG environment variable "
                         "not set.")

    with open(config_path, "r", encoding="UTF-8") as f:
        executers_config_unparsed = json.load(f)

    if len(executers_config_unparsed) == 0:
        raise ValueError("No supported executer types specified.")

    executers_config = {}

    logging.info("Supported executer types:")
    for exec_type, exec_config_unparsed in executers_config_unparsed.items():
        if not isinstance(exec_type, str):
            raise ValueError(f"Apptainer type must be a string: {exec_type}")
        if not isinstance(exec_config_unparsed, dict):
            raise ValueError(f"Apptainer image configuration must be a dict: "
                             f"{exec_config_unparsed}")

        executer_image = exec_config_unparsed.get("image")
        if not isinstance(executer_image, str):
            logging.error("Apptainer image name must be a string: %s",
                          executer_image)
            raise ValueError(
                f"Apptainer image name must be a string: {executer_image}")

        logging.info(" > Executer type: %s", exec_type)
        logging.info("   Apptainer image: %s", executer_image)

        executers_config[exec_type] = ExecuterConfig(image=executer_image)

    return executers_config
