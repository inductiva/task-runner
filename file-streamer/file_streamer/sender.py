# sender.py

import asyncio
import json
import logging
import os

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


async def get_directory_contents(task=""):
    return os.listdir('./' + task)


async def read_file(filename):
    with open(filename, 'rb') as f:
        cnt = f.read()
        return cnt.decode()


async def tail_file(filename, lines=10):
    with open(filename, 'rb') as f:
        f.seek(0, 2)
        block_size = 1024
        block_num = -1
        blocks = []
        while f.tell() + (block_num * block_size) > 0:
            try:
                f.seek(block_num * block_size, 2)
            except OSError:
                f.seek(0)
                blocks.append(f.read())
                break
            blocks.append(f.read(block_size))
            block_num -= 1
        content = b''.join(reversed(blocks))
        return b'\n'.join(content.split(b'\n')[-lines:])


async def create_peer_connection():
    pc = RTCPeerConnection()
    pc.configuration = {"iceServers": ICE_SERVERS}

    @pc.on("datachannel")
    def on_datachannel(channel):

        @channel.on("message")
        async def on_message(message):
            if message == "list":
                contents = await get_directory_contents()
                channel.send(json.dumps({"type": "list", "data": contents}))

            elif message == "pwd":
                logging.info("GOT pwd")
                channel.send(json.dumps({"type": "pwd", "data": os.getcwd()}))

            elif message.startswith(("download:", "cat:")):
                filename = message.split(":")[1]
                content = await read_file(filename)
                logging.info("Sending file %s to peer", filename)
                channel.send(
                    json.dumps({
                        "type": message.split(":")[0],
                        "filename": filename,
                        "data": content
                    }))

            elif message.startswith("tail:"):
                filename = message.split(":")[1]
                content = await tail_file(filename)
                channel.send(content)

            elif message.startswith("cd:"):
                path = message.split(":")[1]
                os.chdir(path)
                contents = await get_directory_contents()
                channel.send(json.dumps({"type": "cd", "data": contents}))

    return pc


async def main():
    os.chdir('/workdir')
    async with aiohttp.ClientSession() as session:
        await session.post(f"{SIGNALING_SERVER}/register",
                           json={"clientId": "taskid_123"})

        while True:
            async with session.get(
                    f"{SIGNALING_SERVER}/message?clientId=taskid_123") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['type'] == 'offer':
                        pc = await create_peer_connection()
                        await pc.setRemoteDescription(
                            RTCSessionDescription(sdp=data['sdp'],
                                                  type=data['type']))
                        answer = await pc.createAnswer()
                        await pc.setLocalDescription(answer)
                        await session.post(f"{SIGNALING_SERVER}/offer",
                                           json={
                                               "receiverId": data['senderId'],
                                               "type": "answer",
                                               "sdp": pc.localDescription.sdp
                                           })


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
