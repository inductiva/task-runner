import asyncio
import json
import logging
import os

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from file_operations import DownloadFile, Operation, OperationError
from operation_response import OperationResponse, OperationStatus


class ClientConnection:

    def __init__(self, task_id, ice_url):
        # STUN/TURN server configuration
        # ICE (Interactive Connectivity Establishment) server helps
        # establish a peer-to-peer connection by discovering and negotiating
        # network paths, including handling NAT traversal and firewall
        # issues, using STUN and TURN protocols.
        # https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols
        ice_servers = [
            RTCIceServer(f"stun:{ice_url}"),
            RTCIceServer(f"turn:{ice_url}")
        ]
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
        self.path = os.path.join(task_id, "output", "artifacts")

    async def setup_connection(self, data):
        channel_closed = asyncio.Event()

        @self.pc.on("datachannel")
        async def on_datachannel(channel):

            @channel.on("message")
            async def on_message(message):
                message = json.loads(message)
                response = OperationResponse()
                try:
                    operation = Operation.from_request(message)
                except (OperationError, ValueError) as e:
                    response = OperationResponse(status=OperationStatus.INVALID,
                                                 message=str(e))
                    channel.send(response.to_json_string())
                    return

                operation.path = self.path
                while not channel_closed.is_set():
                    try:
                        # DownloadFile uses direct streaming to support large
                        # files and avoid memory issues and WebRTC message size
                        # limits
                        if isinstance(operation, DownloadFile):
                            response.message = await operation.execute(channel)
                        else:
                            response.message = await operation.execute()
                    except OperationError as e:
                        response = OperationResponse(
                            status=OperationStatus.ERROR, message=str(e))
                    finally:
                        if response.message is not None:
                            channel.send(response.to_json_string())

                    follow_mode = message.get("follow", False)
                    if follow_mode and not isinstance(operation, DownloadFile):
                        await asyncio.sleep(1)
                    else:
                        break

            @channel.on("close")
            async def on_close():
                channel_closed.set()
                await self.close()
                logging.info("PeerConnection closed")

        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=data['sdp'], type=data['type']))
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        return self.pc

    async def close(self):
        await self.pc.close()
