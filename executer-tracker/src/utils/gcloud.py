"""Util functions to get info about the GCloud VM the executer is on."""
from dataclasses import dataclass
from typing import Dict, Optional
from utils import bool_string_to_bool
import requests

METADATA_SERVER_URL = "http://metadata.google.internal"
METADATA_URL = \
    f"{METADATA_SERVER_URL}/computeMetadata/v1/instance/"
METADATA_FLAVOR_HEADER = "Metadata-Flavor"
METADATA_FLAVOR_HEADER_VALUE = "Google"


def is_running_on_gcloud_vm() -> bool:
    """Check if the executer is running on a GCloud VM.

    Uses the internal metadata server to check if the VM is running on GCloud.
    Details:
     - https://cloud.google.com/compute/docs/instances/detect-compute-engine
    """
    try:
        r = requests.get(
            url=METADATA_SERVER_URL,
            headers={METADATA_FLAVOR_HEADER: METADATA_FLAVOR_HEADER_VALUE},
            timeout=5,
        )
    except requests.exceptions.ConnectionError:
        return False

    return r.status_code == 200 and \
        r.headers.get(METADATA_FLAVOR_HEADER) == "Google"


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


def get_vm_metadata_full() -> Optional[Dict]:
    """Get all metadata for the VM from the internal metadata server.

    Returns all metadata as a dict.
    """

    url_suffix = "?recursive=true"
    r = _get_vm_metadata(url_suffix)
    if r is None:
        return None

    return r.json()


def get_vm_metadata_value(key: str) -> Optional[str]:
    """Get metadata value for the VM from the internal metadata server.

    Returns the value for the given key as a string.
    """
    r = _get_vm_metadata(key)
    if r is None:
        return None

    return r.text


@dataclass
class GCloudVMInfo:
    type: str
    name: str
    zone: str
    id: str
    preemptible: bool


def get_vm_info() -> Optional[GCloudVMInfo]:
    """Get the VM information from the internal metadata server."""
    metadata = get_vm_metadata_full()
    if not metadata:
        return None

    # Remove the attributes field, as it contains ssh keys
    del metadata["attributes"]
    preemptible = bool_string_to_bool(metadata["scheduling"]["preemptible"])

    return GCloudVMInfo(
        type=metadata["machineType"],
        name=metadata["name"],
        id=str(metadata["id"]),
        zone=metadata["zone"],
        preemptible=preemptible,
    )


def is_vm_preempted() -> bool:
    """Check if the VM was preempted.

    Uses the internal metadata server to check if the VM was preempted.
    Details:
    https://cloud.google.com/compute/docs/instances/create-use-preemptible#determine_if_a_vm_was_preempted # pylint: disable=line-too-long
    """
    preempted = get_vm_metadata_value(key="preempted")
    if preempted is None:
        return False

    return bool_string_to_bool(preempted)
