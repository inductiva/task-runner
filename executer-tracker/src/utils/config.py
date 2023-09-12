"""Util functions related to executer-tracker config."""
import json
import os
import dataclasses
from typing import Dict, Optional
from uuid import UUID
from absl import logging
from docker.errors import ImageNotFound

from utils import gcloud


def get_resource_pool_id() -> Optional[UUID]:
    """Get resource pool ID from env variable or GCloud VM metadata.

    First checks if the RESOURCE_POOL env variable is set. If not, tries to
    get the value from the GCloud VM metadata.

    Returns:
        Resource pool ID or None if not found.
    """

    resource_pool_str = os.getenv("RESOURCE_POOL")
    if resource_pool_str is None:
        resource_pool_str = gcloud.get_vm_metadata_value(
            "attributes/resource_pool")

    logging.info("Resource pool: %s", resource_pool_str)

    if not resource_pool_str:  # check if is None or empty string
        return None

    return UUID(resource_pool_str)


@dataclasses.dataclass
class ExecuterConfig:
    image: str
    use_gpu: bool = False


def load_executers_config(docker_client) -> Dict[str, ExecuterConfig]:
    """Load supported executer types from config file.

    Config file is specified by the EXECUTERS_CONFIG environment
    variable. It should be a JSON file with the following format:
        {
            "executer_type_1": {
                "image": "docker_image_1",
                "gpu": true
            },
            "gromacs": {
                "image": "gromacs-img",
                "gpu": true
            },
            "openfoam": {
                "image": "openfoam-img",
                "gpu": false
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
            raise ValueError(f"Executer type must be a string: {exec_type}")
        if not isinstance(exec_config_unparsed, dict):
            raise ValueError(
                f"Docker image must be a dict: {exec_config_unparsed}")

        docker_image = exec_config_unparsed.get("image")
        if not isinstance(docker_image, str):
            logging.error("Docker image must be a string: %s", docker_image)
            raise ValueError(f"Docker image must be a string: {docker_image}")

        use_gpu = exec_config_unparsed.get("gpu", False)

        logging.info(" > Executer type: %s", exec_type)
        logging.info("   Docker image: %s", docker_image)
        if use_gpu:
            logging.info("   Use GPU: %s", use_gpu)

        try:
            docker_client.images.get(docker_image)
        except ImageNotFound as e:
            logging.error("Docker image not found: %s", docker_image)
            raise e

        executers_config[exec_type] = ExecuterConfig(image=docker_image,
                                                     use_gpu=use_gpu)

    return executers_config
