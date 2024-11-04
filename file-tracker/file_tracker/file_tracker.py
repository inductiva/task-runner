import asyncio
import json
import logging
import os
from collections import deque

import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription

SIGNALING_SERVER = "http://34.79.246.4:6000"

# STUN/TURN server configuration
ICE_SERVERS = [{
    "urls": ["stun:34.79.246.4:3478"]
}, {
    "urls": ["turn:34.79.246.4:3478"]
}]

INTERNAL_ICE_SERVERS = [{
    "urls": ["stun:10.132.0.71:3478"]
}, {
    "urls": ["turn:10.132.0.71:3478"]
}]

MAX_MESSAGE_SIZE = 1000 * 16  # 16KB


class FileTracker:

    def __init__(self):
        pass

    async def listen(self, task_id):
        self.running = True
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
                            pc = await create_peer_connection(task_id)
                            await pc.setRemoteDescription(
                                RTCSessionDescription(sdp=data['sdp'],
                                                      type=data['type']))
                            answer = await pc.createAnswer()
                            await pc.setLocalDescription(answer)
                            await session.post(
                                f"{SIGNALING_SERVER}/offer",
                                json={
                                    "receiverId": data['senderId'],
                                    "type": "answer",
                                    "sdp": pc.localDescription.sdp
                                })
            logging.info("Stopped listening for messages")

    async def close(self):
        self.running = False


async def get_directory_contents(path):
    contents = []
    dir = os.listdir(path)
    for file in dir:
        if os.path.isdir(path + file + "/"):
            contents.append(
                {file: await get_directory_contents(path + file + "/")})
        else:
            contents.append(file)
    return contents


async def tail_file(filename, lines=10):
    with open(filename, 'rb') as f:
        f.seek(0, 2)  # Seek to the end of the file
        block_size = 1024
        blocks = deque()
        read_lines = 0

        while f.tell() > 0:
            current_block_size = min(block_size, f.tell())

            f.seek(-current_block_size, 1)
            block = f.read(current_block_size)
            f.seek(
                -current_block_size, 1
            )  # Move the cursor back to the position before reading the block

            read_lines += block.count(b'\n')  # Count lines for early stopping
            blocks.appendleft(block)
            if read_lines > lines:
                break

        content = b''.join(blocks)
        return b'\n'.join(content.split(b'\n')[-lines:])


async def create_peer_connection(task_id):
    pc = RTCPeerConnection()
    pc.configuration = {"iceServers": ICE_SERVERS}
    path = task_id + "/output/artifacts/"

    @pc.on("datachannel")
    def on_datachannel(channel):

        @channel.on("message")
        async def on_message(message):
            if message == "ls":
                contents = await get_directory_contents(path)
                channel.send(json.dumps(contents))

            elif message.startswith("tail:"):
                filename = message.split(":")[1]
                content = await tail_file(filename)
                channel.send(content)

        @channel.on("close")
        async def on_close():
            await pc.close()
            logging.info("PeerConnection closed")

    return pc
