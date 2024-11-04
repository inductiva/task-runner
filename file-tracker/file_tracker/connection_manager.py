import asyncio
import logging

import aiohttp
from client_connection import ClientConnection

SIGNALING_SERVER = "http://34.79.246.4:6000"


class ConnectionManager:

    def __init__(self):
        pass

    async def listen(self, task_id):
        self.running = True
        self.connections = []
        asyncio.create_task(self._listen_loop(task_id))

    async def _listen_loop(self, task_id):
        async with aiohttp.ClientSession() as session:
            await session.post(f"{SIGNALING_SERVER}/register",
                               json={"clientId": task_id})

            while self.running:
                logging.info("Listening for connections")
                async with session.get(
                        f"{SIGNALING_SERVER}/message?clientId={task_id}"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['type'] == 'offer':
                            client_connection = ClientConnection(task_id)
                            pc = await client_connection.setup_connection(data)
                            await session.post(
                                f"{SIGNALING_SERVER}/offer",
                                json={
                                    "receiverId": data['senderId'],
                                    "type": "answer",
                                    "sdp": pc.localDescription.sdp
                                })
                            self.connections.append(client_connection)
            logging.info("Stopped listening for messages")

    async def close(self):
        self.running = False
        for connection in self.connections:
            await connection.close()
