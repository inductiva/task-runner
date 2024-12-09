"""Generic shell commands class."""
import dataclasses
import shlex
from typing import Optional

from task_runner import executers


@dataclasses.dataclass
class MPICommandConfig():
    version: str
    args: list[str] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict):
        options = data.get("options", {})
        if options is None:
            options = {}

        args = []

        for name, value in options.items():
            if isinstance(value, bool) and not value:
                continue

            args.append(f"--{name}")

            if not isinstance(value, bool):
                args.append(str(value))

        return cls(version=data["version"], args=args)


class Command():
    """Class for shell commands.

    This class deals with the shell commands, represented by string with the
    command itself and one or more prompts, when applicable. It performs basic
    security validation of the command.

    Attributes:
        cmd (str): The command, given as a string.
        prompt (list[str]): Command prompts, given as a list of strings.

    Example:
        >>> command = Command("gmx pdb2gmx -f protein.pdb", prompts=["amber94"])
    """

    def __init__(
        self,
        cmd: str,
        prompts: Optional[list[str]] = None,
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
    def from_dict(cls, data: dict):
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

    def _tokenize(self, cmd) -> list[str]:
        """Tokenize command"""

        return shlex.split(cmd)

    def _check_security(self, tokens, prompts):
        """Check command security."""
        if not tokens:
            raise ValueError(f"Command '{' '.join(tokens)}' is empty.")

        cmd_elems = tokens + prompts

        for cmd_elem in cmd_elems:
            executers.security.check_command_elem_security(cmd_elem)
