"""Security checks for the executers."""

import re


def check_command_elem_security(cmd_elem):
    """Checks for security issues in a command element."""

    maximum_elem_len = 256
    if len(cmd_elem) > maximum_elem_len:
        raise ValueError(f"Command element '{cmd_elem}' is too long.")

    if cmd_elem == "":
        raise ValueError(f"Command element '{cmd_elem}' is empty.")

    # Assure that command element is not a know operator for concatenating
    # multiple commands in a single line.
    # Blacklist: contains ";" or "|" or two "&".
    pattern = r".*[;|&]{1,2}.*"
    if re.match(pattern, cmd_elem):
        raise ValueError(
            f"Command element '{cmd_elem}' contains invalid characters.")
