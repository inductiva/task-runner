"""Util functions related to executer-tracker config."""
import os
from typing import Optional
from uuid import UUID

from utils import gcloud

from absl import logging


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
