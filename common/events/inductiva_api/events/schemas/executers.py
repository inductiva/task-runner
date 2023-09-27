"""Events related to executers."""
import datetime
from typing import Any, Dict, List, Literal, Union, Optional

from inductiva_api.events.schemas import Event
from inductiva_api.task_status import ExecuterTerminationReason
from pydantic import UUID4, BaseModel, Field
from typing_extensions import Annotated


class GCloudHostInfo(BaseModel):
    """Info about Google Cloud machine hosting the executer."""
    host_type: Literal["gcloud"]
    vm_type: str
    vm_name: str
    vm_id: str
    preemptible: bool
    vm_metadata: Dict[str, Any]


class InductivaHostInfo(BaseModel):
    """Info about the Inductiva server hosting the executer."""
    host_type: Literal["inductiva-hardware"]
    hostname: str


class ExecuterCreate(BaseModel):
    """Info for creating an executer."""
    create_time: datetime.datetime
    supported_executer_types: List[str]
    cpu_count_logical: int
    cpu_count_physical: int
    memory: int
    cpu_info: str
    resource_pool_id: Optional[UUID4]

    # Use the "type" field to discriminate between different executer types.
    host_info: Annotated[Union[GCloudHostInfo, InductivaHostInfo],
                         Field(discriminator="host_type")]


# Shared properties of executer events.
class ExecuterEvent(Event):
    uuid: UUID4


# Executer created event.
class ExecuterCreated(ExecuterEvent):
    executer_info: ExecuterCreate


# Executer terminated event.
class ExecuterTerminated(ExecuterEvent):
    reason: ExecuterTerminationReason
    detail: Optional[str]
    stopped_tasks: List[str]
