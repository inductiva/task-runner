"""Executer tracker for schim"""
import os
import shutil

from executer_tracker import executers


class SCHISMExecuter(executers.BaseExecuter):
    """Executer class for the SCHISM simulator."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        n_vcpus = self.args.n_vcpus
        num_scribes = self.arg.num_scribes

        # The simulator expects a directory "outputs" to store the outputs.
        os.mkdir(os.path.join(artifcats_dir, "outputs"))

        cmd = executers.Command(
            f"mpirun --np {n_vcpus} /schism/build/bin/pschism {num_scribes}")

        self.run_subprocess(cmd, self.artifacts_dir)
