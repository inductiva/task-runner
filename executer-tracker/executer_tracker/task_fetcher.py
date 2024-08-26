import abc

from typing_extensions import override


class BaseTaskFetcher(abc.ABC):

    @abc.abstractmethod
    def get_task(self, block_s: int):
        pass


class RedisTaskFetcher(BaseTaskFetcher):
    """Implementation of a task fetcher using Redis streams."""

    _DELIVER_NEW_MESSAGES = ">"
    _TASK_KEYS_SET = "task_keys_suffixes"

    def __init__(
        self,
        connection,
        stream,
        consumer_group,
        consumer_name,
    ):
        self._conn = connection
        self._stream = stream
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name
        self._stream_entry_id = None

    @override
    def get_task(self, block_s: int):
        timeout_ms = block_s * 1000
        resp = self._conn.xreadgroup(
            groupname=self._consumer_group,
            consumername=self._consumer_name,
            # Using the following ID will get messages that haven't
            # been delivered to any consumer.
            streams={self._stream: self._DELIVER_NEW_MESSAGES},
            count=1,  # reads one item at a time.
            block=timeout_ms,
        )
        if not resp:
            return None

        _, messages = resp[0]
        _, request = messages[0]

        return request


class WebApiTaskFetcher(BaseTaskFetcher):
    """Implementation of the task execution long polling the Web API."""

    def __init__(self, api_client, executer_tracker_id):
        self._api_client = api_client
        self._id = executer_tracker_id

    @override
    def get_task(self, block_s: int):
        return self._api_client.get_task(self._id, block_s)
