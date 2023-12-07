"""Generic shell commands class."""

from abc import ABC, abstractmethod
import shlex
from typing import List, Optional

from executer_tracker import executers


class Command(ABC):
    """Class for shell commands.

    This class deals with the shell commands, represented by string with the
    command itself and one or more prompts, when applicable. It performs basic
    security validation of the command.

    Attributes:
        cmd (str): The command, given as a string.
        prompt (List[str]): Command prompts, given as a list of strings.

    Example:
        >>> command = Command("gmx pdb2gmx -f protein.pdb", prompts=["amber94"])
        >>> str(command)
        "gmx pdb2gmx -f protein.pdb <<EOD0 \n amber94 \n EOD0"
    """

    def __init__(self, cmd: str, prompts: Optional[List[str]] = None):

        if prompts is None:
            prompts = []

        self.check_security(cmd, prompts)

        self.cmd = cmd
        self.prompts = prompts

    def __str__(self):
        """Builds the command as a string."""

        return self.cmd + " " + self._build_prompts_as_str()

    def _build_prompts_as_str(self):
        """Builds the command prompts as a string."""

        prompts = []

        for index, value in enumerate(self.prompts):
            prompts.append(f"<<EOD{index} \n {value} \n EOD{index}")

        return " ".join(prompts)

    @staticmethod
    @abstractmethod
    def check_security(cmd, prompts):
        """Checks for security issues."""

        tokens = shlex.split(cmd)

        if not tokens:
            raise ValueError(f"Command '{' '.join(tokens)}' is empty.")

        cmd_elems = tokens + prompts

        for cmd_elem in cmd_elems:
            executers.security.check_command_elem_security(cmd_elem)
