"""Generic OpenFOAM executer."""
import os
import shlex
import shutil
import psutil

from executer_tracker import executers


class OpenFOAMCommand(executers.Command):
    """OpenFOAM command."""

    def __init__(self, cmd, prompts, n_cores):
        cmd = self.process_openfoam_command(cmd, n_cores)
        # This is used because OpenFOAM has some setup performed by
        # the bashrc file, so we use bash to run the command.
        cmd = f"/launch.sh \"{cmd}\""
        super().__init__(cmd, prompts)

    @staticmethod
    def process_openfoam_command(cmd, n_cores):
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

        sane_tokens = list(map(lambda x: f"'{x}'" if " " in x else x, tokens))
        command_instruction = sane_tokens[0].lower()
        openfoam_command = sane_tokens[1]
        flags = sane_tokens[2:]

        if command_instruction == "runparallel" and n_cores > 1:
            command = (
                f"mpirun --allow-run-as-root -np "
                f"{n_cores} {openfoam_command} {' '.join(flags)} -parallel")
        elif command_instruction == "runparallel" and n_cores == 1:
            command = f"{openfoam_command} {' '.join(flags)}"
        elif command_instruction == "runapplication":
            command = f"{openfoam_command} {' '.join(flags)}"
        else:
            raise ValueError("Invalid instruction for OpenFOAM. "
                             "Valid instructions are: runParallel"
                             " and runApplication.")

        return command


class OpenFOAMExecuter(executers.BaseExecuter):
    """OpenFOAM executer."""

    @staticmethod
    def validate_parallel_execution(openfoam_command, n_cores):
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

        if n_cores == 1:
            if openfoam_cmd in commands_excluded_of_singlecore_execution:
                return False

        return True

    def add_n_cores_in_input_files(self, n_cores):
        """Add the number of cores to the input files.

        To run in parallel, the number of cores must be specified
        in the file decomposeParDict. This method adds the maximum
        number of cores in the machine to this file.

        This changes whatever number of cores was specified in the
        input file.

        Args:
            n_cores: Number of cores to run the simulation on.
        """

        set_n_cores_command = {
            "cmd": (f"runApplication foamDictionary system/decomposeParDict "
                    f"-entry numberOfSubdomains -set {n_cores}"),
            "prompts": []
        }
        cmd = OpenFOAMCommand(set_n_cores_command["cmd"],
                              set_n_cores_command["prompts"], n_cores)
        self.run_subprocess(cmd, self.artifacts_dir)

    def execute(self):
        n_cores = psutil.cpu_count(logical=False)
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        commands = self.args.commands

        # Does not run for n_cores=1, since the decomposeParDict this changes
        # is not used in this case.
        if n_cores > 1:
            self.add_n_cores_in_input_files(n_cores)

        for command in commands:
            command = OpenFOAMCommand(command["cmd"], command["prompts"],
                                      n_cores)
            if self.validate_parallel_execution(command, n_cores):
                self.run_subprocess(command, self.artifacts_dir)

        if n_cores > 1:
            for core in range(n_cores):
                processor_dir = f"processor{core}"
                shutil.rmtree(os.path.join(self.artifacts_dir, processor_dir))
