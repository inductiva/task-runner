import glob
import os
import re
import threading
import uuid
from enum import Enum
from typing import Dict, Optional

from absl import logging
from pydantic import BaseModel

import task_runner
from task_runner import events


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

        for path in self._resolve_paths(sim_dir, file_path):
            if os.path.exists(path):
                return True
        return False

    def _check_file_regex(self, sim_dir: str, file_path: str,
                          regex: str) -> list[str]:
        """Checks if the file exists and its content matches the regex."""
        matches: list[str] = []
        for path in self._resolve_paths(sim_dir, file_path):
            if not os.path.exists(path):
                continue
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                matches.extend(re.findall(regex, content))
        return matches

    def _resolve_paths(self, sim_dir: str, file_path: str) -> list[str]:
        """Resolve file_path which may be a literal path or use '*' wildcard.

        If file_path contains '*', it uses shell-style wildcard expansion
        (glob) relative to sim_dir. Matching is non-recursive: '*' does not
        cross directory boundaries; e.g., '*' matches files in sim_dir, and
        'dir/*' matches files directly under sim_dir/dir.
        Otherwise, file_path is treated as a literal relative path.
        """
        if not file_path:
            return []

        # Reject absolute paths
        if os.path.isabs(file_path):
            return []

        if '*' in file_path:
            pattern = os.path.join(sim_dir, file_path)
            matches = glob.glob(pattern)
            return [p for p in matches if os.path.isfile(p)]

        return [os.path.join(sim_dir, file_path)]

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
                    matches = self._check_file_regex(sim_dir,
                                                     observer.file_path,
                                                     observer.regex)
                    if matches:
                        self.stop_observing(observer_id)
                        extra_params = {"captured": matches}
                        self._event_logger.log(
                            events.ObserverTriggered(id=task_id,
                                                     observer_id=observer_id,
                                                     extra_params=extra_params))

            self._stop_event.wait(self._check_interval_seconds)

    def stop(self):
        self._stop_event.set()
