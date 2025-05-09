import os
import re
import threading
from enum import Enum
from typing import Dict, Union

from absl import logging
from inductiva_api import events
from pydantic import BaseModel, validator

import task_runner


class ObserverType(str, Enum):
    FILE_EXISTS = "FileExistsObserver"
    FILE_REGEX = "FileRegexObserver"


class FileExistObserver(BaseModel):
    path: str


class FileRegexObserver(BaseModel):
    path: str
    regex: str

    @validator('regex')
    def valid_regex(cls, v: str) -> str:  # noqa: N805
        try:
            re.compile(v)
            return v
        except re.error as e:
            raise ValueError(f"Invalid regex: {v} - {e}")


class Observer(BaseModel):
    observer_id: str
    observer_type: ObserverType
    observer: Union[FileExistObserver, FileRegexObserver]


class ObserverManager:

    def __init__(
        self,
        event_logger: task_runner.BaseEventLogger,
        check_interval_seconds: int = 5,
    ):
        self._event_logger = event_logger
        self._observers: Dict[str, Observer] = {}
        self._check_interval_seconds = check_interval_seconds
        self._stop_event = threading.Event()

    def start_observing(self, observer: Observer):
        """Adds an observer to the manager."""

        self._observers[observer.observer_id] = observer

    def stop_observing(self, observer_id: str):
        """Removes an observer from the manager."""

        if observer_id in self._observers:
            del self._observers[observer_id]

    def _check_file_exists(self, sim_dir: str,
                           config: FileExistObserver) -> bool:
        """Checks if the file specified exists."""

        return os.path.exists(os.path.join(sim_dir, config.path))

    def _check_file_regex(self, sim_dir: str,
                          config: FileRegexObserver) -> bool:
        """Checks if the file exists and its content matches the regex."""
        path = os.path.join(sim_dir, config.path)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return re.search(config.regex, content) is not None
            except Exception:  # noqa: BLE001
                return False

    def run(self, sim_dir, task_id):
        """The main loop for checking observers."""

        while not self._stop_event.is_set():
            observers_to_check = self._observers.copy()
            for observer_id, observer in observers_to_check.items():
                observer_type = observer.observer_type
                logging.info(
                    "Checking observer %s",
                    observer_id,
                )

                if observer_type == ObserverType.FILE_EXISTS:
                    if self._check_file_exists(sim_dir, observer.observer):
                        self.stop_observing(observer_id)
                        self._event_logger.log(
                            events.ObserverTriggered(id=task_id,
                                                     observer_id=observer_id))

                elif observer_type == ObserverType.FILE_REGEX:
                    if self._check_file_regex(sim_dir, observer.observer):
                        self.stop_observing(observer_id)
                        self._event_logger.log(
                            events.ObserverTriggered(id=task_id,
                                                     observer_id=observer_id))

            self._stop_event.wait(self._check_interval_seconds)

    def stop(self):
        self._stop_event.set()
