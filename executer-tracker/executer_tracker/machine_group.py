import logging
import uuid

from executer_tracker import ApiClient


class MachineGroupInfo:

    def __init__(self, id: uuid.UUID, name: str, local_mode: bool) -> None:

        self.id = id
        self.name = name
        self.local_mode = local_mode

    def get_machine_group_id(self, api_client: ApiClient) -> uuid.UUID:
        if self.id:
            logging.info("Specified machine group: %s", self.id)
            return self.id

        if (self.name and (machine_group_id :=
                           api_client.get_machine_group_id_by_name(self.name))):
            logging.info("Specified machine group exists: %s", self.name)
            return machine_group_id

        if not self.local_mode:
            raise ValueError("No machine group specified.")

        logging.info("No machine group specified. \
                Creating a new local machine group...")
        machine_group_id = api_client.create_local_machine_group(
            machine_group_name=self.name)

        return machine_group_id
