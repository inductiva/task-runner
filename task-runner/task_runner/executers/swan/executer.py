"""Run simulation with SWAN."""
from task_runner import executers
from task_runner.executers import mpi_configuration
from task_runner.utils import loki

import os
import shutil


class SWANExecuter(executers.BaseExecuter):
    """Executer class for the SWAN simulator."""
    def execute(self):
        sim_binary = self.args.command
        input_filename = self.args.input_filename

        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        if self.args.use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

        if sim_binary == "swanrun":
            if input_filename.endswith(".swn"):
                #remove the .swn extension
                cmd_str = f"{sim_binary} -input {input_filename[:-4]}"
            else:
                cmd_str = f"{sim_binary} -input {input_filename}"
        elif sim_binary == "swan.exe":
                cmd_str = f"{sim_binary}"
        else:
            raise ValueError("Invalid sim_binary")

        cmd = executers.Command(cmd_str,
                                is_mpi=True)

        self.run_subprocess(cmd, self.artifacts_dir)

