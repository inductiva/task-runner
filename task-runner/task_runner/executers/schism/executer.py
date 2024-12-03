"""Task-Runner for schim"""
import os
import shutil

from task_runner import executers


class SCHISMExecuter(executers.BaseExecuter):
    """Executer class for the SCHISM simulator."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        num_scribes = self.args.num_scribes

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        if self.args.use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

        # The simulator expects a directory "outputs" to store the outputs.
        os.mkdir(os.path.join(self.artifacts_dir, "outputs"))

        cmd = executers.Command(f"/schism/build/bin/pschism {num_scribes}",
                                is_mpi=True)

        self.run_subprocess(cmd, self.artifacts_dir)
