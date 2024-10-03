"""Generic OpenFOAM executer."""
import os
import shlex
import shutil
from typing import Tuple

from task_runner import executers


class OpenFOAMCommand(executers.Command):
    """OpenFOAM command."""

    def __init__(self, cmd, prompts, n_vcpus):
        cmd, is_mpi = self.process_openfoam_command(cmd, n_vcpus)
        # This is used because OpenFOAM has some setup performed by
        # the bashrc file, so we use bash to run the command.
        cmd = f"/launch.sh \"{cmd}\""
        super().__init__(cmd, prompts, is_mpi=is_mpi)

    @staticmethod
    def process_openfoam_command(cmd, n_vcpus) -> Tuple[str, bool]:
        """Set the appropriate command for OpenFOAM.

        Define the appropriate command to be run inside the machine
        based on the command passed by the user - `runApplication`
        or `runParallel``.

        Returns:
            Command to be executed in the executer."""

        tokens = shlex.split(cmd)
        # Adding single quotes to args with whitespaces in them,
        # which shlex removes.
        # Example: "runApplication transformPoints -scale '(1e-3 1e-3 1e-3)'"

        sane_tokens = list(  # noqa: C417
            map(lambda x: f"'{x}'" if " " in x else x, tokens))
        command_instruction = sane_tokens[0].lower()
        openfoam_command = sane_tokens[1]
        flags = sane_tokens[2:]

        command = f"{openfoam_command} {' '.join(flags)}"
        is_mpi = False

        if command_instruction not in ("runparallel", "runapplication"):
            raise ValueError("Invalid instruction for OpenFOAM. "
                             "Valid instructions are: runParallel"
                             " and runApplication.")

        if command_instruction == "runparallel" and n_vcpus > 1:
            command += " -parallel"
            is_mpi = True

        return command, is_mpi


class OpenFOAMExecuter(executers.BaseExecuter):
    """OpenFOAM executer."""

    @staticmethod
    def validate_parallel_execution(openfoam_command, n_vcpus):
        """Validate if a command can be run in parallel.

        Some OpenFOAM commands cannot and/or should not
        be run in parallel. This method checks if the command
        is one of these commands. The goal is to have a single
        list of commands to run sequentially or in parallel.

        This list might be updated over time.

        Returns:
            Return True if the command should be run in parallel,
            and False if not.
        """

        commands_excluded_of_singlecore_execution = [
            "decomposePar", "reconstructPar", "reconstructParMesh"
        ]

        # The commands which aren't parallel have
        # command name as the first token.
        # The second token in the openfoam_command is the actual command,
        # which is what we want to check. The first element is the util
        # script we use to run the command.
        openfoam_cmd = shlex.split(openfoam_command.args[1])[0]

        if n_vcpus == 1:
            if openfoam_cmd in commands_excluded_of_singlecore_execution:
                return False

        return True

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        use_hwthread = bool(self.args.use_hwthread)
        if use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

        n_vcpus = self.args.n_vcpus or self.count_vcpus(use_hwthread)
        self.mpi_config.extra_args.extend(["-np", f"{n_vcpus}"])

        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        commands = self.args.commands

        for command in commands:
            command = OpenFOAMCommand(command["cmd"], command["prompts"],
                                      n_vcpus)
            if self.validate_parallel_execution(command, n_vcpus):
                self.run_subprocess(command, self.artifacts_dir)
