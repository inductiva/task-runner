"""Util function for synchronous writting of info files"""


def update_stdout_file(std_file, offset, stdout_stream):
    """Writes the new content to the stdout live file

    Writes the new contents of the stdout file from the last written
    position. Returns the last byte position of the whole file (e.g. if
    a file has 1024 bytes position=1024). Posterior calls of this function
    with offset = (previous position) will write to the stream only
    the contents that correspont to a byte position posterior to the offset,
    i.e., the new content in the stdout file"""

    with open(std_file, "rb") as f_src:
        f_src.seek(offset)
        new_stdout = f_src.read()

        stdout_stream.write(new_stdout)
        position = f_src.tell()

    return position
