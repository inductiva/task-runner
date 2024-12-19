import os
from collections import deque

MAX_SIZE = 1024 * 14  # 14KB


class OperationError(Exception):
    pass


def ls(path):
    contents = []
    dir = os.listdir(path)
    for file in dir:
        file_path = os.path.join(path, file)
        if os.path.isdir(file_path):
            contents.append({file: ls(file_path)})
        else:
            contents.append(file)
    return contents


def tail(path_to_file, filename, lines=10):
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
            f.seek(
                -current_block_size, 1
            )  # Move the cursor back to the position before reading the block

            read_lines += block.count(b'\n')  # Count lines for early stopping
            blocks.appendleft(block)
            current_size += current_block_size
            if read_lines > lines or current_size > MAX_SIZE:
                break
        try:
            content = b''.join(blocks).decode()
        except UnicodeDecodeError:
            raise OperationError(f"File is not a text file: {filename}")
        return content.split('\n')[-lines:]
