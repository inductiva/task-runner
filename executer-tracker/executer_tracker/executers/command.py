"""Generic shell commands class."""
import dataclasses
import shlex
from typing import Dict, List, Optional

from executer_tracker import executers


@dataclasses.dataclass
class MPICommandConfig():
    version: str

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(version=data["version"])


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

    def __init__(
        self,
        cmd: str,
        prompts: Optional[List[str]] = None,
        is_mpi: bool = False,
        mpi_config: Optional[MPICommandConfig] = None,
    ):

        if prompts is None:
            prompts = []

        self.args = self._tokenize(cmd)
        self.prompts = prompts
        self.is_mpi = is_mpi
        self.mpi_config = mpi_config
        self._check_security(self.args, prompts)

    @classmethod
    def from_dict(cls, data: Dict):
        """Create an instance from a dictionary."""
        mpi_config_data = data.get("mpi_config")
        mpi_config = MPICommandConfig.from_dict(
            mpi_config_data) if mpi_config_data else None

        return cls(
            cmd=data["cmd"],
            prompts=data.get("prompts", []),
            is_mpi=mpi_config is not None,
            mpi_config=mpi_config,
        )

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
