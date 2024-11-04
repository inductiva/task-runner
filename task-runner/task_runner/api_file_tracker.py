import asyncio

SERVER_HOST = 'localhost'
SERVER_PORT = 5000


class ApiFileTracker:

    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.host = host
        self.port = port

    def start(self, task_id):
        message = "start:" + task_id
        asyncio.run(self._message(message))

    def stop(self, task_id):
        message = "stop:" + task_id
        asyncio.run(self._message(message))

    async def _message(self, message):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        writer.write(message.encode())
        await writer.drain()

        data = await reader.read(100)
        response = data.decode()
        assert response == "ACK"

        writer.close()
        await writer.wait_closed()
