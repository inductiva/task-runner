# sender.py

import asyncio
import json
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


async def get_directory_contents():
    return os.listdir('.')


async def read_file(filename):
    with open(filename, 'rb') as f:
        cnt = f.read()
        print(f'file content: {cnt}')
        return cnt


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
                channel.send(json.dumps(contents))

            elif message.startswith("download:"):
                filename = message.split(":")[1]
                content = await read_file(filename)
                channel.send(content)

            elif message.startswith("tail:"):
                filename = message.split(":")[1]
                content = await tail_file(filename)
                channel.send(content)

    return pc


async def main():
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
    asyncio.run(main())
