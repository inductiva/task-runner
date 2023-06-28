"""Util functions to get info about the GCloud VM the executer is on."""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
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


def get_vm_metadata(key: Optional[str] = None) -> Optional[Union[Dict, str]]:
    """Get the metadata for the VM from the internal metadata server.

    Args:
        key: if provided, get the value for the given key. If not provided, get
            the entire metadata as JSON.
    """

    get_recursive = True
    url_suffix = "?recursive=true"
    if key:
        url_suffix = key
        get_recursive = False

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

    return r.json() if get_recursive else r.text


@dataclass
class GCloudVMInfo:
    type: str
    name: str
    id: str
    preemptible: bool
    metadata: Dict[str, Any]


def get_vm_info() -> Optional[GCloudVMInfo]:
    """Get the VM information from the internal metadata server."""
    metadata = get_vm_metadata()
    if not metadata:
        return None
    if not isinstance(metadata, dict):
        return None

    # Remove the attributes field, as it contains ssh keys
    del metadata["attributes"]
    preemptible = bool_string_to_bool(metadata["scheduling"]["preemptible"])

    return GCloudVMInfo(
        type=metadata["machineType"],
        name=metadata["name"],
        id=str(metadata["id"]),
        preemptible=preemptible,
        metadata=metadata,
    )


def is_vm_preempted() -> bool:
    """Check if the VM was preempted.

    Uses the internal metadata server to check if the VM was preempted.
    Details:
    https://cloud.google.com/compute/docs/instances/create-use-preemptible#determine_if_a_vm_was_preempted # pylint: disable=line-too-long
    """
    preempted = get_vm_metadata(key="preempted")
    if not isinstance(preempted, str):
        return False

    return bool_string_to_bool(preempted)
