"""Generic Fire simulation with FDS."""
import os
import shutil

from task_runner import executers


class FDSExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run FDS."""

    def check_smokeview_exec(self):
        """Check conditions to Smokeview execution.

        Conditions:
            - Check if users passed a configuration path;
            - Check if the configuration path exists;
            - Find the output file for smokeview;

        Returns:
            If any of the checks don't pass, return None.
            Else, return the smokeview output file.
        """
        if self.args.post_processing_config is None:
            return None

        smokeview_script = os.path.join(self.artifacts_dir,
                                        self.args.post_processing_config)

        if os.path.exists(smokeview_script):
            # Find Smokeview simulation input file
            # No more than one file exists.
            smokeview_file = [
                file for file in os.listdir(self.artifacts_dir)
                if file.endswith(".smv")
            ]

            if smokeview_file:
                return os.path.join(self.artifacts_dir, smokeview_file[0])
        else:
            return None

    def execute(self):
        sim_dir = os.path.join(self.working_dir, self.args.sim_dir)
        input_filename = self.args.input_filename

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        if self.args.use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

        # Copy the input files to the artifacts directory
        shutil.copytree(sim_dir, self.artifacts_dir, dirs_exist_ok=True)

        #fds bin
        fds_bin = "/opt/fds/Build/ompi_gnu_linux/fds_ompi_gnu_linux"

        cmd = executers.Command(f"{fds_bin} {input_filename}", is_mpi=True)
        self.run_subprocess(cmd, working_dir=self.artifacts_dir)
