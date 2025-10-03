import logging
import uuid

from task_runner import ApiClient
from task_runner.utils import config


class MachineGroupInfo:

    def __init__(self, id: uuid.UUID, name: str, local_mode: bool):
        self.id = id
        self.name = name
        self.local_mode = local_mode

    @classmethod
    def from_api(cls, api_client: ApiClient):
        machine_group_info = cls(
            id=config.get_machine_group_id(),
            name=config.get_machine_group_name(),
            local_mode=config.is_machine_group_local(),
        )

        if machine_group_info.id:
            logging.info("Specified machine group: %s", machine_group_info.id)
            return machine_group_info

        if machine_group_info.name and (
                machine_group_id :=
                api_client.get_started_machine_group_id_by_name(
                    machine_group_info.name)):
            logging.info("Specified machine group exists: %s",
                         machine_group_info.name)
            machine_group_info.id = machine_group_id
            return machine_group_info

        if not machine_group_info.local_mode:
            raise ValueError("No machine group specified.")

        logging.info("No machine group specified. \
                Creating a new local machine group...")
        machine_group_info.id = api_client.create_local_machine_group(
            machine_group_name=machine_group_info.name)

        return machine_group_info
