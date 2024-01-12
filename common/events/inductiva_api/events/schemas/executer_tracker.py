"""Schemas of events issued by the executer-tracker."""
from typing import List, Literal, Union, Optional
from typing_extensions import Annotated
import uuid
import datetime
import pydantic

import inductiva_api.events.schemas as event_schemas
from inductiva_api import task_status


class GCloudHostInfo(pydantic.BaseModel):
    """Info about Google Cloud machine hosting the executer."""
    host_type: Literal["gcloud"]
    vm_type: str
    vm_name: str
    vm_id: str
    vm_zone: str
    preemptible: bool


class InductivaHostInfo(pydantic.BaseModel):
    """Info about the Inductiva server hosting the executer."""
    host_type: Literal["inductiva-hardware"]
    hostname: str


class ExecuterTrackerRegisterInfo(pydantic.BaseModel):
    """Info for creating an executer."""
    create_time: datetime.datetime
    supported_executer_types: List[str]
    cpu_count_logical: int
    cpu_count_physical: int
    memory: int
    git_commit_hash: str
    machine_group_id: Optional[uuid.UUID]
    mpi_cluster: bool = False
    num_mpi_hosts: int = 1

    # Use the "type" field to discriminate between different executer types.
    host_info: Annotated[Union[GCloudHostInfo, InductivaHostInfo],
                         pydantic.Field(discriminator="host_type")]


# Shared properties of executer tracker events.
class ExecuterTrackerEvent(event_schemas.Event):
    uuid: uuid.UUID


# Executer tracker up event.
class ExecuterTrackerRegistered(ExecuterTrackerEvent):
    machine_info: ExecuterTrackerRegisterInfo


# Executer tracker down event.
class ExecuterTrackerTerminated(ExecuterTrackerEvent):
    reason: task_status.ExecuterTerminationReason
    detail: Optional[str]
    stopped_tasks: List[str]
