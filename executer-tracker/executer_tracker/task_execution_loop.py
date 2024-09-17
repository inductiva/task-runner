import time
from typing import Optional

from absl import logging

from executer_tracker import BaseTaskFetcher, TaskRequestHandler


def start_loop(
    task_fetcher: BaseTaskFetcher,
    request_handler: TaskRequestHandler,
    block_s: int = 30,
    max_idle_timeout: Optional[int] = None,
):
    logging.info("Starting execution loop ...")

    idle_timestamp = time.time()
    while True:
        try:
            if max_idle_timeout and time.time(
            ) - idle_timestamp >= max_idle_timeout:
                raise TimeoutError("Max idle time reached")

            logging.info("Waiting for requests...")
            request = task_fetcher.get_task(block_s=block_s)

            if request is not None:
                logging.info("Received request:")
                logging.info(" --> %s", request)
                request_handler(request)

                # Update the start time to avoid killing the machine
                idle_timestamp = time.time()

        except ConnectionError as e:
            logging.info("ERROR CONNECTION: %s", str(e))
