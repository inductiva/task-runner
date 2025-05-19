import time
from typing import Optional

from absl import logging
from requests.exceptions import ConnectionError, ReadTimeout

from task_runner import BaseTaskFetcher, TaskRequestHandler
from task_runner.api_client import HTTPStatus
from task_runner.cleanup import ScaleDownTimeoutError


def start_loop(
    task_fetcher: BaseTaskFetcher,
    request_handler: TaskRequestHandler,
    block_s: int = 1,
    max_idle_timeout: Optional[int] = None,
):
    logging.info("Starting execution loop ...")

    idle_timestamp = time.time()
    while True:
        try:
            if max_idle_timeout and time.time(
            ) - idle_timestamp >= max_idle_timeout:
                raise ScaleDownTimeoutError()

            logging.info("Waiting for requests...")
            request = task_fetcher.get_task(block_s=block_s)

            if request.status == HTTPStatus.SUCCESS:
                logging.info("Received request:")
                logging.info(" --> %s", request.data)
                request_handler(request.data)

                # Update the start time to avoid killing the machine
                idle_timestamp = time.time()
            elif request.status == HTTPStatus.INTERNAL_SERVER_ERROR:
                time.sleep(30)
            else:
                time.sleep(5)

        except ConnectionError as e:
            logging.exception("Connection Error: %s", str(e))
            continue
        except ReadTimeout as e:
            logging.exception("Request timed out: %s", str(e))
            continue
