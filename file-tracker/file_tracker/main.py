import asyncio
import logging
import os

from connection_manager import ConnectionManager
from task_listener import TaskListener


async def main():
    os.chdir('/workdir')

    connection_manager = ConnectionManager()
    task_listener = TaskListener(connection_manager)
    logging.info("Starting task listener")
    await task_listener.start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
