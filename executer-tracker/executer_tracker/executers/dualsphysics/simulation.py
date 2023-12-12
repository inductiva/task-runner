"""Generic SPH simulation with DualSPHysics.

This script uses DualSPHysics to perform a simulation.
"""
import os
import shutil
import shlex
import glob

from absl import app, logging

import executers_common


def get_available_commands():
    """Create a dict mapping commands to executables.
    
    Here, we assume that commands are the core name of the
    executable, e.g.: PartVTK_linux64 -> PartVTK.

    Returns the reverse map with lower case for simplicity: 
        partvtk -> BIN_DIR/PartVTK_linux64
    """
    bin_dir = os.getenv("DUALSPHYSICS_BIN_DIR")
    binaries_list = glob.glob("*_linux64", root_dir=bin_dir)

    # Binaries are of the form: PartVTK_linux64.
    # Users only need to pass PartVTK.
    available_commands = {}
    for binary in binaries_list:
        cmd_exec = binary.removesuffix("_linux64").lower()
        available_commands[cmd_exec] = os.path.join(bin_dir, binary)

    return available_commands


class DualSPHysicsCommand(executers_common.Command):
    """DualSPHysics command."""

    def __init__(self, cmd, prompts, device, executables):
        self.executables = executables
        cmd = self.process_dualsphysics_command(cmd, device)
        super().__init__(cmd, prompts)

    @staticmethod
    def check_security(cmd, prompts):
        """Method below takes care of it."""
        pass

    def process_dualsphysics_command(self, cmd, device):
        """Process the command to map to the executable."""

        tokens = shlex.split(cmd)
        cmd_name = tokens[0].lower()

        # Process command for GPU runs. Map to binaries.
        if cmd_name == "dualsphysics":
            if device == "gpu":
                tokens[0] = self.executables["dualsphysics5.2"]
                tokens.insert(1, "-gpu")
            else:
                tokens[0] = self.executables["dualsphysics5.2cpu"]
        elif cmd_name in self.executables.keys():
            tokens[0] = self.executables[cmd_name]
        else:
            raise ValueError(f"{cmd_name} is an invalid "
                             "DualSPHysics command.")

        command = " ".join(tokens)

        return command


class DualSPHysicsExecuter(executers_common.BaseExecuter):
    """Concrete implementation of an Executer to run DualSPHysics."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        commands_to_executables = get_available_commands()

        # TODO: Add support for machines with GPU
        device = "cpu"

        os.chdir(self.artifacts_dir)
        commands = self.args.commands

        for command in commands:
            cmd = DualSPHysicsCommand(command["cmd"], command["prompts"],
                                      device, commands_to_executables)
            self.run_subprocess(str(cmd))


def main(_):
    executer = DualSPHysicsExecuter()
    executer.run()


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
