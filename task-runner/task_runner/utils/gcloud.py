"""Util functions to get info from gcloud."""

from typing import Optional

import requests
from task_runner.utils import bool_string_to_bool

METADATA_SERVER_URL = "http://metadata.google.internal"
METADATA_URL = f"{METADATA_SERVER_URL}/computeMetadata/v1/instance/"
METADATA_FLAVOR_HEADER = "Metadata-Flavor"
METADATA_FLAVOR_HEADER_VALUE = "Google"


def _get_vm_metadata(url_suffix: str):
    url = f"{METADATA_URL}{url_suffix}"

    try:
        r = requests.get(
            url=url,
            headers={METADATA_FLAVOR_HEADER: METADATA_FLAVOR_HEADER_VALUE},
            timeout=5,
        )
    except requests.exceptions.ConnectionError:
        return None

    if r.status_code != 200:
        return None

    return r


def get_vm_metadata_value(key: str) -> Optional[str]:
    """Get metadata value for the VM from the internal metadata server.

    Returns the value for the given key as a string.
    """
    r = _get_vm_metadata(key)
    if r is None:
        return None

    return r.text


def is_vm_preempted() -> bool:
    """Check if the VM was preempted.

    Uses the internal metadata server to check if the VM was preempted.
    Details:
    https://cloud.google.com/compute/docs/instances/create-use-preemptible#determine_if_a_vm_was_preempted
    """  # noqa: E501
    preempted = get_vm_metadata_value(key="preempted")
    if preempted is None:
        return False

    return bool_string_to_bool(preempted)
