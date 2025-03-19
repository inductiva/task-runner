"""Generic shell commands class."""
import dataclasses
import shlex
from typing import Optional


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
        _check_format(self.args, prompts)

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


def _check_format(tokens, prompts):
    """Check command format."""
    if not tokens:
        raise ValueError(f"Command '{' '.join(tokens)}' is empty.")

    cmd_elems = tokens + prompts

    for cmd_elem in cmd_elems:
        _check_length(cmd_elem)


def _check_length(cmd_elem):
    """Checks for length limits in a command element."""

    maximum_elem_len = 512
    if len(cmd_elem) > maximum_elem_len:
        raise ValueError(f"Command element '{cmd_elem}' is too long.")

    if cmd_elem == "":
        raise ValueError(f"Command element '{cmd_elem}' is empty.")
