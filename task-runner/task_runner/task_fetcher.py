import abc

from typing_extensions import override


class BaseTaskFetcher(abc.ABC):

    @abc.abstractmethod
    def get_task(self, block_s: int):
        pass


class WebApiTaskFetcher(BaseTaskFetcher):
    """Implementation of the task execution long polling the Web API."""

    def __init__(self, api_client, task_runner_id):
        self._api_client = api_client
        self._id = task_runner_id

    @override
    def get_task(self, block_s: int):
        return self._api_client.get_task(self._id, block_s)
