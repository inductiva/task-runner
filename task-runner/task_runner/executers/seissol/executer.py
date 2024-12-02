import os
import shutil

from task_runner.executers import BaseExecuter, command


class SeisSolExecuter(BaseExecuter):
    def execute(self):
        """
        Execute the SeisSol simulation.

        This method runs the SeisSol simulator using the specified input configuration
        and stores the output in the artifacts directory.
        """
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        input_file_path = os.path.join(self.artifacts_dir, self.args.input_filename)

        simulator_binary = "SeisSol_Release_dhsw_4_elastic"

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])
        if self.args.use_hwthread:
            self.mpi_config.extra_args.append("--use-hwthread-cpus")

        cmd = command.Command(
            cmd=f"{simulator_binary} {input_file_path}",
            is_mpi=True,
            mpi_config=self.mpi_config,
        )
        self.run_subprocess(cmd)
