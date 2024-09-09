import abc

from absl import logging
from inductiva_api.events import RedisStreamEventLoggerSync
from inductiva_api.events.schemas import Event
from typing_extensions import override


class BaseEventLogger(abc.ABC):

    @abc.abstractmethod
    def log(self, event):
        pass


class RedisEventLogger(BaseEventLogger):

    def __init__(self, connection):
        self._logger = RedisStreamEventLoggerSync(connection, "events")

    @override
    def log(self, event: Event):
        logging.info("Logging event: %s", event)
        self._logger.log(event)


class WebApiLogger(BaseEventLogger):

    def __init__(self, api_client, executer_tracker_id):
        self._api_client = api_client
        self._executer_tracker_id = executer_tracker_id

    @override
    def log(self, event: Event):
        logging.info("Logging event: %s", event)
        self._api_client.log_event(self._executer_tracker_id, event)
