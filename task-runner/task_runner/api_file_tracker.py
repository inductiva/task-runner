import asyncio
import logging

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000


class ApiFileTracker:

    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.host = host
        self.port = port
        self.started = False

    def start(self, task_id):
        logging.info("Starting task streaming: %s", task_id)
        message = "start:" + task_id
        asyncio.run(self._message(message))

    def stop(self, task_id):
        if self.started:
            logging.info("Stoping task streaming: %s", task_id)
            message = "stop:" + task_id
            asyncio.run(self._message(message))

    async def _message(self, message, num_retries=3):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        while num_retries > 0:
            writer.write(message.encode())
            await writer.drain()

            data = await reader.read(100)
            response = data.decode()

            if response == "ACK":
                break

            num_retries -= 1

        writer.close()
        await writer.wait_closed()
