from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests

METADATA_SERVER_URL = "http://metadata.google.internal"
METADATA_URL = f"{METADATA_SERVER_URL}/computeMetadata/v1/instance/?recursive=true"
METADATE_FLAVOR_HEADER = "Metadata-Flavor"
METADATE_FLAVOR_HEADER_VALUE = "Google"


def is_running_on_gcloud_vm():
    try:
        r = requests.get(
            url=METADATA_SERVER_URL,
            headers={METADATE_FLAVOR_HEADER: METADATE_FLAVOR_HEADER_VALUE},
            timeout=5,
        )
    except requests.exceptions.ConnectionError:
        return False

    return r.status_code == 200 and \
        r.headers.get(METADATE_FLAVOR_HEADER) == "Google"


def get_vm_metadata() -> Optional[Dict]:
    """Get the metadata for the VM from the internal metadata server."""
    try:
        r = requests.get(
            url=METADATA_URL,
            headers={METADATE_FLAVOR_HEADER: METADATE_FLAVOR_HEADER_VALUE},
            timeout=5,
        )
    except requests.exceptions.ConnectionError:
        return None

    if r.status_code != 200:
        return None

    return r.json()


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

    # Remove the attributes field, as it contains ssh keys
    del metadata["attributes"]

    return GCloudVMInfo(
        type=metadata["machineType"],
        name=metadata["name"],
        id=str(metadata["id"]),
        preemptible=bool(metadata["scheduling"]["preemptible"]),
        metadata=metadata,
    )
