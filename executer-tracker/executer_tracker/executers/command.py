"""Generic shell commands class."""
import shlex
from typing import List, Optional

from executer_tracker import executers


class Command():
    """Class for shell commands.

    This class deals with the shell commands, represented by string with the
    command itself and one or more prompts, when applicable. It performs basic
    security validation of the command.

    Attributes:
        cmd (str): The command, given as a string.
        prompt (List[str]): Command prompts, given as a list of strings.

    Example:
        >>> command = Command("gmx pdb2gmx -f protein.pdb", prompts=["amber94"])
    """

    def __init__(self, cmd: str, prompts: Optional[List[str]] = None):

        if prompts is None:
            prompts = []

        self.args = self._tokenize(cmd)
        self.prompts = prompts
        self._check_security(self.args, prompts)

    def _tokenize(self, cmd) -> List[str]:
        """Tokenize command"""

        return shlex.split(cmd)

    def _check_security(self, tokens, prompts):
        """Check command security."""
        if not tokens:
            raise ValueError(f"Command '{' '.join(tokens)}' is empty.")

        cmd_elems = tokens + prompts

        for cmd_elem in cmd_elems:
            executers.security.check_command_elem_security(cmd_elem)
