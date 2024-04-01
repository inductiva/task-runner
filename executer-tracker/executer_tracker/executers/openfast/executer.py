"""Generic OpenFOAM executer."""
import os
import shlex
import shutil
from typing import Tuple

from executer_tracker import executers

class OpenfastCommand(executers.Command):
    """Openfast command."""
    ALLOWED_COMMANDS = [
        "aerodyn_driver", "beamdyn_driver", "feam_driver", "hydrodyn_driver",
        "inflowwind_driver", "moordyn_driver", "openfast", "orca_driver",
        "servodyn_driver", "subdyn_driver", "turbsim", "unsteadyaero_driver"
    ]

    def __init__(self, cmd, prompts):
        cmd = self.process_openfast_command(cmd)

        super().__init__(cmd, prompts, is_mpi=False)

    @staticmethod
    def process_openfast_command(cmd) -> Tuple[str, bool]:
        """Set the appropriate command for Openfast.

        Checks if the command sent is allowed.

        Returns:
            Command to be executed in the executer."""

        tokens = shlex.split(cmd)
        # Adding single quotes to args with whitespaces in them,
        # which shlex removes.
        sane_tokens = list(map(lambda x: f"'{x}'" if " " in x else x, tokens))
        command_instruction = sane_tokens[0].lower()
        openfast_command = sane_tokens[1]
        flags = sane_tokens[2:]

        command = f"{openfast_command} {' '.join(flags)}"

        if command_instruction not in OpenfastCommand.ALLOWED_COMMANDS:
            raise ValueError("Invalid instruction for Openfast. "
                             "Valid instructions are: "
                             f"{OpenfastCommand.ALLOWED_COMMANDS}.")

        return command


class OpenfastExecuter(executers.BaseExecuter):
    """OpenFOAM executer."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        commands = self.args.commands

        for command in commands:
            command = OpenfastCommand(command["cmd"], command["prompts"])
            self.run_subprocess(command, self.artifacts_dir)