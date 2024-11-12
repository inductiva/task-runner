"""Run simulation with SWAN."""
import os
import shutil

from task_runner import executers


class SWANExecuter(executers.BaseExecuter):
    """Executer class for the SWAN simulator."""

    def _create_command(self,binary, input_file, np, is_mpi):
        """Create the command to run the SWAN simulator.
        Args:
            binary (str): The binary to run.
            input_file (str): The input file to run.
            np (int): The number of CPUs to use.
        """
        if input_file.endswith(".swn"):
            input_file = input_file[:-4]
        return executers.Command(f"{binary} -input {input_file} -mpi {np}", is_mpi)
    def execute(self):
        sim_binary = self.args.command
        input_filename = self.args.input_filename
        np = self.args.n_vcpus or 1

        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        # Swanrun uses internal MPI
        # we call apptainer run ... swanrun ... -mpi np
        if sim_binary == "swanrun":
            cmd = self._create_command(sim_binary, input_filename, np, is_mpi=False)

        # we call mpirun ... apptainer ... Swan.exe
        # works with clusters
        elif sim_binary == "swan.exe":
            
            if self.args.n_vcpus:
                self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])
            if self.args.use_hwthread:
                self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])
            
            cmd = executers.Command(sim_binary, is_mpi=True)
        else:
            raise ValueError("Invalid sim_binary")


        self.run_subprocess(cmd, self.artifacts_dir)
