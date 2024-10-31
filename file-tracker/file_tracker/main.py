import asyncio
import logging
import os

from file_tracker import FileTracker
from task_listener import TaskListener


async def main():
    os.chdir('/workdir')

    file_tracker = FileTracker()
    task_listener = TaskListener(file_tracker)
    logging.info("Starting task listener")
    await task_listener.start()
    logging.info("Task listener started")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
