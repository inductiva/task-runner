import abc

from absl import logging
from typing_extensions import override

from task_runner import utils
from task_runner.events.schemas import Event


class BaseEventLogger(abc.ABC):

    @abc.abstractmethod
    def log(self, event):
        pass


class WebApiLogger(BaseEventLogger):

    def __init__(self, api_client, task_runner_id):
        self._api_client = api_client
        self._task_runner_id = task_runner_id

    @utils.retry()
    def _log_event(self, event: Event):
        elapsed_time = (utils.now_utc() - event.timestamp).total_seconds()
        event.elapsed_time_s = elapsed_time
        self._api_client.log_event(self._task_runner_id, event)

    @override
    def log(self, event: Event):
        event_name = event.__class__.__name__
        logging.info("Logging event: %s, %s", event_name, event)
        self._log_event(event)
        logging.info("Event logged: %s", event_name)
