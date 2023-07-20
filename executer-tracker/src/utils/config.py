"""Util functions related to executer-tracker config."""
import json
import os
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


def load_supported_executer_types(docker_client) -> Dict[str, str]:

    config_path = os.getenv("EXECUTER_DOCKER_IMAGES_CONFIG")
    if not config_path:
        raise ValueError("EXECUTER_DOCKER_IMAGES_CONFIG environment variable "
                         "not set.")

    with open(config_path, "r", encoding="UTF-8") as f:
        docker_images = json.load(f)

    if len(docker_images) == 0:
        raise ValueError("No supported executer types specified.")

    logging.info("Supported executer types:")
    for executer_type, docker_image in docker_images.items():
        if not isinstance(executer_type, str):
            raise ValueError(f"Executer type must be a string: {executer_type}")
        if not isinstance(docker_image, str):
            raise ValueError(f"Docker image must be a string: {docker_image}")

        logging.info(" > Executer type: %s", executer_type)
        logging.info("   Docker image: %s", docker_image)

        try:
            docker_client.images.get(docker_image)
        except ImageNotFound as e:
            logging.error("Docker image not found: %s", docker_image)
            raise e

    return docker_images
