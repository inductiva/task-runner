"""This file provides a class to implement MPI executers."""
import os
import shutil
import psutil
import platform

from executer_tracker import executers

# Instructions inside Docker containers are run by the root user (as default),
# so we need to allow Open MPI to be run as root. This is usually strongly
# discouraged, but necessary to run Open MPI inside a container. For further
# details, see https://www.open-mpi.org/doc/v4.1/man1/mpirun.1.php#toc25.
MPI_ALLOW = "--allow-run-as-root"
MPI_DISTRIBUTION_FILENAME = "machinefile"


class MPIExecuter(executers.BaseExecuter):
    """Implementation of a general MPI Executer."""

    def __init__(self, bin_env_var, file_type, sim_specific_input_filename):
        super().__init__()
        self.bin_env_var = bin_env_var
        self.sim_specific_input_filename = sim_specific_input_filename
        self.file_type = file_type

    def create_mpi_distribution_file(self, n_cores: int, node_name: str,
                                     dir_path: str) -> None:
        with open(os.path.join(dir_path, MPI_DISTRIBUTION_FILENAME),
                  "w",
                  encoding="utf-8") as f:
            f.write(f"{node_name} : {n_cores}\n")

    def execute(self):
        sim_dir = self.args.sim_dir
        input_filename = self.args.input_filename
        n_cores = psutil.cpu_count(logical=False)

        mpi_bin = os.getenv("MPIRUN_BIN")
        sim_bin = os.getenv(self.bin_env_var)

        host_name = platform.node()
        if n_cores > 1:
            self.create_mpi_distribution_file(n_cores=n_cores,
                                              node_name=host_name,
                                              dir_path=sim_dir)

        os.chdir(sim_dir)

        if not os.path.exists(input_filename):
            if os.path.exists(f"{input_filename}.{self.file_type}"):
                input_filename = f"{input_filename}.{self.file_type}"
            else:
                raise ValueError(
                    f"A file with name {input_filename} doesn't exist.")

        # Renaming input file as the simulator expects it to be
        os.rename(input_filename, self.sim_specific_input_filename)

        input_files = set(os.listdir())

        self.run_subprocess(f"{mpi_bin} {MPI_ALLOW} -np {n_cores} {sim_bin}")

        all_files = set(os.listdir())
        new_files = all_files - input_files

        for filename in new_files:
            dst_path = os.path.join(self.artifacts_dir, filename)

            if os.path.isfile(filename):
                shutil.copy(filename, dst_path)
            elif os.path.isdir(filename):
                shutil.copytree(filename, dst_path)
