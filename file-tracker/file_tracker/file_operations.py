import abc
import os
from collections import deque


class OperationError(Exception):

    @classmethod
    def from_request(cls, request):
        operation = cls._get_class(request["type"])
        return operation(**request["args"])

    def _get_class(self, type):
        if type == "ls":
            return Ls
        elif type == "tail":
            return Tail
        else:
            raise OperationError(f"Unknown operation type: {type}")

    @abc.abstractmethod
    def execute(self):
        raise NotImplementedError("Subclasses must implement this method")


class Operation:
    pass


class Ls(Operation):

    def __init__(self, path):
        self.path = path

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


class Tail(Operation):

    def __init__(self, filename, lines=10):
        self.filename = filename
        self.lines = lines
        super().__init__()

    def execute(self):
        return self.tail(self.path, self.filename, self.lines)

    def tail(self, path_to_file, filename, lines=10):
        file = os.path.join(path_to_file, filename)
        if not os.path.exists(file):
            raise OperationError(f"File not found: {filename}")
        with open(file, 'rb') as f:
            f.seek(0, 2)  # Seek to the end of the file
            block_size = 1024
            blocks = deque()
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
            except UnicodeDecodeError:
                raise OperationError(f"File is not a text file: {filename}")
            return content.split('\n')[-lines:]
