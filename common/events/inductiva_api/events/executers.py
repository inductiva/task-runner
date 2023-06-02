"""Events related to tasks."""
import datetime
from typing import Annotated, Any, Dict, List, Literal, Union

from inductiva_api.task_status import ExecuterTerminationReason
from pydantic import UUID4, BaseModel, Field

from .event import Event


class GCloud(BaseModel):
    """Executer information specific to google cloud executers.

    The type field is used to discriminate between different executer types,
    when parsing the JSON data in the request body.
    """
    type: Literal["gcloud"]
    vm_type: str
    vm_name: str
    vm_id: str
    preemptible: bool
    vm_metadata: Dict[str, Any]


class Inductiva(BaseModel):
    """Executer information specific to on-premise executers.


    The type field is used to discriminate between different executer types,
    when parsing the JSON data in the request body.
    """
    type: Literal["inductiva-hardware"]


class ExecuterEvent(Event):
    uuid: UUID4


class ExecuterInfo(BaseModel):
    create_time: datetime.datetime
    cpu_count_logical: int
    cpu_count_physical: int
    memory: int
    cpu_info: str
    host_info: Annotated[Union[GCloud, Inductiva], Field(discriminator="type")]


class ExecuterCreated(ExecuterEvent):
    executer_info: ExecuterInfo


class ExecuterTerminated(ExecuterEvent):
    reason: ExecuterTerminationReason
    stopped_tasks: List[str]
