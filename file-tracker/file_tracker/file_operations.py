import abc
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
        operation = cls._get_class(request["type"])
        return operation(**request["args"])

    @classmethod
    def _get_class(cls, type):

        if type in cls.SUPPORTED_OPERATIONS:
            return cls.SUPPORTED_OPERATIONS[type]
        else:
            raise OperationError(f"Unknown operation type: {type}")

    @abc.abstractmethod
    def execute(self):
        raise NotImplementedError("Subclasses must implement this method")


class List(Operation):

    def __init__(self):
        self.path = None

    def execute(self):
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

    def execute(self):
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


class LastModifiedFile(Operation):
    """Class for the LastModifiedFile Operation."""

    def execute(self):
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

    def __init__(self, filename, lines=10):
        self.filename = filename
        self.lines = lines
        self.path = None
        self.last_updated_at = None
        self.cursor = None

    def execute(self):
        if self.cursor:
            return self.get_appended(self.path, self.filename)
        return self.tail(self.path, self.filename, self.lines)

    def tail(self, path_to_file, filename, lines=10):
        file = os.path.join(path_to_file, filename)
        if not os.path.exists(file):
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


# Initialize SUPPORTED_OPERATIONS after defining all classes
Operation.SUPPORTED_OPERATIONS = {
    "ls": List,
    "tail": Tail,
    "top": Top,
    "last_modified_file": LastModifiedFile
}
