import abc

from absl import logging
from inductiva_api.events.schemas import Event
from typing_extensions import override


class BaseEventLogger(abc.ABC):

    @abc.abstractmethod
    def log(self, event):
        pass


class WebApiLogger(BaseEventLogger):

    def __init__(self, api_client, task_runner_id):
        self._api_client = api_client
        self._task_runner_id = task_runner_id

    @override
    def log(self, event: Event):
        logging.info("Logging event: %s", event)
        self._api_client.log_event(self._task_runner_id, event)
