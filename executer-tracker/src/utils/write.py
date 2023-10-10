"""Util function for synchronous writting of info files"""


def find_difference(old_string, new_string):
    """Return the new contents in new_string

    The stdout file is continuously uploaded to the user as the simulation
    runs. In order for only the recent updates to be uploaded we need to
    check if there is any new content in the stdout file and return it
    accordingly."""
    if old_string == new_string:
        return None
    return new_string[len(old_string):]


def update_stdout_file(std_file, stdout_live, stdout_stream):
    """Writes the new content to the stdout_live file

    Checks the new contents of the stdout file and uploads to the
    stdout stream"""

    with open(std_file, "rb") as f_src:
        new_stdout = f_src.read().decode("utf-8")
        stdout_difference = find_difference(stdout_live, new_stdout)

        if stdout_difference is not None:
            binary_data = stdout_difference.encode("utf-8")
            stdout_stream.write(binary_data)
            stdout_live += stdout_difference

    return stdout_live
