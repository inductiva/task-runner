"""Generic GROMACS executer.

This script wraps the GROMACS's CLI.
"""

import os
import shlex
import shutil
from executer_tracker import executers


class GROMACSCommand(executers.Command):
    """GROMACS command."""

    @staticmethod
    def check_security(cmd, prompts):
        executers.Command.check_security(cmd, prompts)

        tokens = shlex.split(cmd)

        if tokens[0] != "gmx":
            raise ValueError("The command must start with 'gmx'.")


class GROMACS(executers.BaseExecuter):
    """Concrete implementation of an Executer to run GROMACS."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        commands = self.args.commands

        for command in commands:
            cmd = GROMACSCommand(command["cmd"], command["prompts"])
            self.run_subprocess(str(cmd), self.artifacts_dir)
