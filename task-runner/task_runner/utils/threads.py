"""Utility functions for working with threads."""
import threading


class ExceptionThread(threading.Thread):
    """Thread that stores exceptions for handling in the parent thread.
    After joining the thread, the parent thread can check if the
    exception attribute is not None and handle it accordingly
    (e.g., re-raise it).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = None

    def run(self):
        try:
            super().run()
        except Exception as exception:  # noqa: BLE001
            self.exception = exception
