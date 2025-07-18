import os
import re
import threading
import uuid
from enum import Enum
from typing import Dict, Optional

from absl import logging
from inductiva_api import events
from pydantic import BaseModel

import task_runner


class ObserverType(str, Enum):
    FILE_EXISTS = "file_exists_observer"
    FILE_REGEX = "file_regex_observer"


class Observer(BaseModel):
    observer_id: uuid.UUID
    observer_type: ObserverType
    task_id: str
    file_path: Optional[str] = None
    regex: Optional[str] = None


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

    def _check_file_exists(self, sim_dir: str, file_path: str) -> bool:
        """Checks if the file specified exists."""

        return os.path.exists(os.path.join(sim_dir, file_path))

    def _check_file_regex(self, sim_dir: str, file_path: str,
                          regex: str) -> bool:
        """Checks if the file exists and its content matches the regex."""
        path = os.path.join(sim_dir, file_path)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return re.search(regex, content) is not None
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
                    if self._check_file_exists(sim_dir, observer.file_path):
                        self.stop_observing(observer_id)
                        self._event_logger.log(
                            events.ObserverTriggered(id=task_id,
                                                     observer_id=observer_id))

                elif observer_type == ObserverType.FILE_REGEX:
                    if self._check_file_regex(sim_dir, observer.file_path,
                                              observer.regex):
                        self.stop_observing(observer_id)
                        self._event_logger.log(
                            events.ObserverTriggered(id=task_id,
                                                     observer_id=observer_id))

            self._stop_event.wait(self._check_interval_seconds)

    def stop(self):
        self._stop_event.set()
