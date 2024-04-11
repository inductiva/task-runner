"""Generic SPH simulation with DualSPHysics.

This script uses DualSPHysics to perform a simulation.
"""
import os
import shlex
import shutil

from executer_tracker import executers


class DualSPHysicsCommand(executers.Command):
    """DualSPHysics command."""

    def __init__(self, cmd, prompts, device):
        cmd = self.process_dualsphysics_command(cmd, device)
        super().__init__(cmd, prompts)

    def process_dualsphysics_command(self, cmd, device):
        """Process the command to map to the executable."""

        tokens = shlex.split(cmd)
        cmd_name = tokens[0].lower()

        # Process command for GPU runs. Map to binaries.
        if cmd_name == "dualsphysics":
            if device == "gpu":
                tokens[0] = "dualsphysics5.2"
                tokens.insert(1, "-gpu")
            else:
                tokens[0] = "dualsphysics5.2cpu"

        bin_dir = "/DualSPHysics_v5.2/bin/linux"
        tokens[0] = os.path.join(bin_dir, tokens[0])

        command = " ".join(tokens)

        return command


class DualSPHysicsExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run DualSPHysics."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        # TODO: Add support for machines with GPU
        device = "cpu"

        commands = self.args.commands

        for command in commands:
            cmd = DualSPHysicsCommand(command["cmd"], command["prompts"],
                                      device)
            self.run_subprocess(cmd, working_dir=self.artifacts_dir)
