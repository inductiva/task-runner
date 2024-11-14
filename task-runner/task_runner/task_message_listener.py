import abc
import time
import uuid

from typing_extensions import override

import task_runner


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
        api_client: task_runner.ApiClient,
        task_runner_id: uuid.UUID,
        block_s: int = 30,
    ):
        self._api_client = api_client
        self._block_s = block_s
        self._task_runner_id = task_runner_id

    @override
    def receive(self, task_id: str):
        while True:
            message = self._api_client.receive_task_message(
                self._task_runner_id,
                task_id,
                block_s=self._block_s,
            )
            if message.status == task_runner.HTTPStatus.SUCCESS:
                return message.data

            if message.status == task_runner.HTTPStatus.INTERNAL_SERVER_ERROR:
                time.sleep(30)

    @override
    def unblock(self, task_id: str):
        self._api_client.unblock_task_message_listeners(
            self._task_runner_id,
            task_id,
        )
