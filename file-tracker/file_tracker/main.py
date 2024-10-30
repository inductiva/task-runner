import asyncio
import logging
import os

from task_listener import TaskListener


async def main():
    os.chdir('/workdir')

    task_coordinator = 0
    task_listener = TaskListener(task_coordinator)
    logging.info("Starting task listener")
    await task_listener.start()
    logging.info("Task listener started")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
