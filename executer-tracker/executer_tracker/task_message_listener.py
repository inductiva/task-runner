import abc
import uuid
from typing import Optional

from typing_extensions import override

import executer_tracker
from executer_tracker import utils


class BaseTaskMessageListener(abc.ABC):

    @abc.abstractmethod
    def receive(self, task_id: str):
        pass

    @abc.abstractmethod
    def unblock(self, task_id: str):
        pass


class RedisTaskMessageListener(BaseTaskMessageListener):
    _TASK_COMMANDS_QUEUE_SUFFIX = "commands"
    _UNBLOCK_COMMAND = "done"

    def __init__(self, connection):
        self._conn = connection

    @override
    def receive(self, task_id: str) -> Optional[str]:
        queue = utils.make_task_key(task_id, self._TASK_COMMANDS_QUEUE_SUFFIX)
        msg = self._conn.brpop(queue)
        return msg[1] if msg is not None else None

    @override
    def unblock(self, task_id: str):
        queue = utils.make_task_key(task_id, self._TASK_COMMANDS_QUEUE_SUFFIX)
        self._conn.lpush(queue, self._UNBLOCK_COMMAND)


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
