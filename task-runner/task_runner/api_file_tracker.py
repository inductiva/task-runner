import asyncio
import logging

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000


class ApiFileTracker:

    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.host = host
        self.port = port

    def start(self, task_id):
        logging.info("Starting task streaming: %s", task_id)
        message = "start:" + task_id
        asyncio.run(self._message(message))

    def stop(self, task_id):
        logging.info("Stoping task streaming: %s", task_id)
        message = "stop:" + task_id
        asyncio.run(self._message(message))

    async def _message(self, message):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        logging.info("Sending message: %s", message)
        writer.write(message.encode())
        await writer.drain()

        data = await reader.read(100)
        response = data.decode()
        logging.info("Received response: %s", response)
        assert response == "ACK"

        writer.close()
        await writer.wait_closed()
