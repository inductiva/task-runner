"""Run simulation with SWAN."""
import os
import shutil

from task_runner import executers


class SWANExecuter(executers.BaseExecuter):
    """Executer class for the SWAN simulator."""

    def execute(self):
        sim_binary = self.args.command
        input_filename = self.args.input_filename
        np = self.args.n_vcpus

        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        # Swanrun uses internal MPI
        # we call apptainer run ... swanrun ... -mpi np
        if sim_binary == "swanrun":
            # if no np is provided, default to 1
            np = np or 1
            if input_filename.endswith(".swn"):
                #remove the .swn extension
                cmd_str = f"{sim_binary} -input {input_filename[:-4]} -mpi {np}"
            else:
                cmd_str = f"{sim_binary} -input {input_filename} -mpi {np}"
            
            cmd = executers.Command(cmd_str, is_mpi=False)
        # we call mpirun ... apptainer ... Swan.exe
        # works with clusters
        elif sim_binary == "swan.exe":
            
            if self.args.n_vcpus:
                self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])
            if self.args.use_hwthread:
                self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

            cmd_str = f"{sim_binary}"
            cmd = executers.Command(cmd_str, is_mpi=True)
        else:
            raise ValueError("Invalid sim_binary")


        self.run_subprocess(cmd, self.artifacts_dir)
