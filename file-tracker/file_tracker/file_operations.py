import os
from collections import deque


async def ls(path):
    contents = []
    dir = os.listdir(path)
    for file in dir:
        file_path = os.path.join(path, file)
        print(file_path)
        if os.path.isdir(file_path):
            contents.append({file: await ls(file_path)})
        else:
            contents.append(file)
    return contents


async def tail(filename, lines=10):
    if not os.path.exists(filename):
        return ["Error: File does not exist."]
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

        content = b''.join(blocks).decode()
        return content.split('\n')[-lines:]
