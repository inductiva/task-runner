"""Util function for synchronous writting of info files"""


def update_stdout_file(std_file, offset, stdout_stream):
    """Writes the new content to the stdout live file

    Writes the new contents of the stdout file from the last written
    position. Returns the position of in the whole file, meaning
    that if posterior calls of this function with offset = previous
    position will write to the stream the new contents"""

    with open(std_file, "rb") as f_src:
        f_src.seek(offset)
        new_stdout = f_src.read()

        stdout_stream.write(new_stdout)
        position = f_src.tell()

    return position
