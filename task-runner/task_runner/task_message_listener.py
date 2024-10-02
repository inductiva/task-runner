import abc
import uuid

import executer_tracker
from typing_extensions import override


class BaseTaskMessageListener(abc.ABC):

    @abc.abstractmethod
    def receive(self, task_id: str):
        pass

    @abc.abstractmethod
    def unblock(self, task_id: str):
        pass


class WebApiTaskMessageListener(BaseTaskMessageListener):

    def __init__(
        self,
        api_client: executer_tracker.ApiClient,
        executer_tracker_id: uuid.UUID,
        block_s: int = 30,
    ):
        self._api_client = api_client
        self._block_s = block_s
        self._executer_tracker_id = executer_tracker_id

    @override
    def receive(self, task_id: str):
        while True:
            message = self._api_client.receive_task_message(
                self._executer_tracker_id,
                task_id,
                block_s=self._block_s,
            )
            if message is not None:
                return message

    @override
    def unblock(self, task_id: str):
        self._api_client.unblock_task_message_listeners(
            self._executer_tracker_id,
            task_id,
        )
