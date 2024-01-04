"""This file provides a class to implement MPI executers."""
from typing import Optional
import os
import shutil

from executer_tracker import executers
from executer_tracker.executers import mpi_configuration

# Instructions inside Docker containers are run by the root user (as default),
# so we need to allow Open MPI to be run as root. This is usually strongly
# discouraged, but necessary to run Open MPI inside a container. For further
# details, see https://www.open-mpi.org/doc/v4.1/man1/mpirun.1.php#toc25.
MPI_ALLOW = "--allow-run-as-root"
MPI_DISTRIBUTION_FILENAME = "machinefile"


class MPIExecuter(executers.BaseExecuter):
    """Implementation of a general MPI Executer."""

    def __init__(self, working_dir, container_image,
                 mpi_config: Optional[mpi_configuration.MPIConfiguration],
                 sim_binary, file_type, sim_specific_input_filename):
        super().__init__(working_dir, container_image, mpi_config)
        self.sim_binary = sim_binary
        self.sim_specific_input_filename = sim_specific_input_filename
        self.file_type = file_type

    def create_mpi_distribution_file(self, n_cores: int, node_name: str,
                                     dir_path: str) -> None:
        with open(os.path.join(dir_path, MPI_DISTRIBUTION_FILENAME),
                  "w",
                  encoding="utf-8") as f:
            f.write(f"{node_name} : {n_cores}\n")

    def execute(self):
        sim_dir = os.path.join(self.working_dir, self.args.sim_dir)
        input_filename = self.args.input_filename

        input_file_full_path = os.path.join(sim_dir, input_filename)

        if not os.path.exists(input_file_full_path):
            if os.path.exists(f"{input_file_full_path}.{self.file_type}"):
                input_filename = f"{input_file_full_path}.{self.file_type}"
            else:
                raise ValueError(
                    f"A file with name {input_filename} doesn't exist.")

        # Renaming input file as the simulator expects it to be
        os.rename(input_file_full_path,
                  os.path.join(sim_dir, self.sim_specific_input_filename))

        input_files = set(os.listdir(sim_dir))

        cmd = executers.Command(self.sim_binary, is_mpi=True)
        self.run_subprocess(cmd, working_dir=sim_dir)

        all_files = set(os.listdir(sim_dir))
        new_files = all_files - input_files

        for filename in new_files:
            dst_path = os.path.join(self.artifacts_dir, filename)
            src_path = os.path.join(sim_dir, filename)

            if os.path.isfile(src_path):
                shutil.copy(src_path, dst_path)
            elif os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
