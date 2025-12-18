import abc
import asyncio
import base64
import json
import os
import subprocess
import time
from collections import deque


class OperationError(Exception):
    pass


class Operation:

    #defined at the end of the document
    SUPPORTED_OPERATIONS = {}

    @classmethod
    def from_request(cls, request):
        operation_type = request["type"]
        operation = cls._get_class(operation_type)
        args = request.get("args", {})

        if "follow" in request and operation == DownloadFile:
            args["follow"] = request["follow"]

        return operation(**args)

    @classmethod
    def _get_class(cls, type):
        if type in cls.SUPPORTED_OPERATIONS:
            return cls.SUPPORTED_OPERATIONS[type]
        else:
            raise OperationError(f"Unknown operation type: {type}")

    @abc.abstractmethod
    async def execute(self):
        raise NotImplementedError("Subclasses must implement this method")


class List(Operation):

    def __init__(self):
        self.path = None

    async def execute(self):
        return self.ls(self.path)

    def ls(self, path):
        contents = []
        dir = os.listdir(path)
        for file in dir:
            file_path = os.path.join(path, file)
            if os.path.isdir(file_path):
                contents.append({file: self.ls(file_path)})
            else:
                contents.append(file)
        return contents


class Top(Operation):
    """Class for the Top Operation."""

    async def execute(self):
        return self.top()

    def top(self) -> str:
        """Run the top command and return the output.

        Will only run the top command once and return the output.
        """
        result = subprocess.run(["top", "-b", "-H", "-n", "1"],
                                capture_output=True,
                                check=False,
                                text=True)
        return result.stdout


LAST_MODIFIED_FILE_PATH_SUFFIX = "output/artifacts/output_update.csv"
METRICS_FILE_PATH_SUFFIX = "output/artifacts/system_metrics.csv"
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64KB


class LastModifiedFile(Operation):
    """Class for the LastModifiedFile Operation."""

    async def execute(self):
        return self.last_modified_file()

    def last_modified_file(self) -> str:
        most_recent_file = None
        time_since_last_mod = None
        most_recent_timestamp = 0

        directory = os.getcwd()

        # Walk through the directory recursively
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                # Get the timestamp of the file's last modification
                timestamp = os.path.getmtime(file_path)

                if file_path.endswith(LAST_MODIFIED_FILE_PATH_SUFFIX) or \
                        file_path.endswith(METRICS_FILE_PATH_SUFFIX):
                    continue

                # Check if this file is the most recently modified
                if timestamp > most_recent_timestamp:
                    most_recent_file = file_path
                    most_recent_timestamp = timestamp

        # Get the current timestamp (now)
        now_timestamp = time.time()

        # If a most recent file exists, calculate time since last modification
        if most_recent_file:
            time_since_last_mod = now_timestamp - most_recent_timestamp

        ret_dic = {
            "most_recent_file": most_recent_file,
            "most_recent_timestamp": most_recent_timestamp,
            "now_timestamp": now_timestamp,
            "time_since_last_mod": time_since_last_mod
        }

        return ret_dic


class Tail(Operation):

    def __init__(self, filename, lines=10, wait=False):
        self.filename = filename
        self.lines = lines
        self.path = None
        self.last_updated_at = None
        self.cursor = None
        self.wait = wait

    async def _wait_for_file(self, file, interval=1):
        while not os.path.exists(file):
            await asyncio.sleep(interval)

    async def execute(self):
        if self.cursor:
            return self.get_appended(self.path, self.filename)
        return await self.tail(self.path, self.filename, self.lines)

    async def tail(self, path_to_file, filename, lines=10, interval=1):
        file = os.path.join(path_to_file, filename)

        if self.wait:
            await self._wait_for_file(file, interval)
        elif not os.path.exists(file):
            raise OperationError(f"File not found: {filename}")

        self.last_updated_at = os.path.getmtime(file)
        blocks = deque()
        with open(file, 'rb') as f:
            f.seek(0, 2)  # Seek to the end of the file
            self.cursor = f.tell()
            block_size = 1024
            current_size = 0
            read_lines = 0

            while f.tell() > 0:
                current_block_size = min(block_size, f.tell())

                f.seek(-current_block_size, 1)
                block = f.read(current_block_size)
                f.seek(-current_block_size, 1)  # Move the cursor back to the
                # position before reading the block

                read_lines += block.count(
                    b'\n')  # Count lines for early stopping
                blocks.appendleft(block)
                current_size += current_block_size
                if read_lines > lines:
                    break
        try:
            content = b''.join(blocks).decode()
            if content[-1] == '\n':
                content = content[:-1]
        except UnicodeDecodeError:
            raise OperationError(f"File is not a text file: {filename}")
        return content.split('\n')[-lines:]

    def get_appended(self, path_to_file, filename):
        file = os.path.join(path_to_file, filename)
        if not os.path.exists(file):
            return None

        current_updated_time = os.path.getmtime(file)
        if self.last_updated_at == current_updated_time:
            return None

        self.last_updated_at = current_updated_time

        content = None
        with open(file, 'rb') as f:
            f.seek(self.cursor)
            content = f.read()
            self.cursor = f.tell()
        try:
            content = content.decode()
            if content[-1] == '\n':
                content = content[:-1]
        except UnicodeDecodeError:
            raise OperationError(f"File is not a text file: {filename}")
        return content.split('\n')


class DownloadFile(Operation):

    def __init__(self, file_path, chunk_size=DEFAULT_CHUNK_SIZE, follow=False):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.chunk_size = chunk_size
        self.follow = follow
        self.path = None

    async def execute(self, channel):
        try:
            full_path = os.path.join(self.path, self.file_path)
            if not os.path.exists(full_path):
                raise OperationError(f"File not found: {self.file_path}")

            if self.follow:
                # Real-time streaming mode - stream file as it's being written
                await self._stream_realtime_file(channel, full_path)
            else:
                # Standard download mode - download existing file
                await self._stream_static_file(channel, full_path)

        except Exception as e:  # noqa: BLE001
            self._send_error(channel, str(e))

    async def _stream_static_file(self, channel, file_path):
        file_size = os.path.getsize(file_path)
        self._send_file_metadata(channel, file_size)

        chunk_count = 0
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break

                chunk_count += 1
                self._send_chunk(channel, chunk, chunk_count)

        self._send_complete(channel, chunk_count, file_size)

    async def _stream_realtime_file(self, channel, file_path, interval=1):
        self._send_file_metadata(channel, None)

        chunk_count = 0
        total_size = 0

        # Stream file content continuously
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    # No more data, wait a bit
                    await asyncio.sleep(interval)
                    continue

                chunk_count += 1
                total_size += len(chunk)
                self._send_chunk(channel, chunk, chunk_count)

    def _send_error(self, channel, error_message):
        message = {
            "status": "error",
            "message": {
                "type": "download_error",
                "error": error_message
            }
        }
        channel.send(json.dumps(message))

    def _send_file_metadata(self, channel, total_size):
        message = {
            "status": "success",
            "message": {
                "type": "download_info",
                "filename": self.filename,
                "total_size": total_size
            }
        }
        channel.send(json.dumps(message))

    def _send_chunk(self, channel, chunk, chunk_number):
        chunk_b64 = base64.b64encode(chunk).decode('utf-8')
        message = {
            "status": "success",
            "message": {
                "type": "download_chunk",
                "chunk_number": chunk_number,
                "chunk_size": len(chunk),
                "data": chunk_b64
            }
        }
        channel.send(json.dumps(message))

    def _send_complete(self, channel, chunk_count, total_size):
        message = {
            "status": "success",
            "message": {
                "type": "download_complete",
                "filename": self.filename,
                "total_chunks": chunk_count,
                "total_size": total_size
            }
        }
        channel.send(json.dumps(message))


# Initialize SUPPORTED_OPERATIONS after defining all classes
Operation.SUPPORTED_OPERATIONS = {
    "ls": List,
    "tail": Tail,
    "top": Top,
    "last_modified_file": LastModifiedFile,
    "download_file": DownloadFile
}
