import asyncio
import logging
import signal
import sys
import threading


class TerminationHandler:

    def __init__(self, connection_manager):
        self._lock = threading.Lock()
        self._terminating = False
        self._connection_manager = connection_manager

    def terminate(self):
        with self._lock:
            if self._terminating:
                return False
            self._terminating = True

        asyncio.run(self._connection_manager.close())


def get_signal_handler(termination_handler):

    def handler(signum, _):
        logging.info("Caught signal %s.", signal.Signals(signum).name)
        if termination_handler.terminate():
            sys.exit()

    return handler


def setup_cleanup_handlers(termination_handler):

    signal_handler = get_signal_handler(termination_handler)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
