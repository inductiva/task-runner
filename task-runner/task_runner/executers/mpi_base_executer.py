"""This file provides a class to implement MPI executers."""
import os
import shutil

from task_runner import executers
from task_runner.executers import mpi_configuration
from task_runner.utils import loki

# Instructions inside Docker containers are run by the root user (as default),
# so we need to allow Open MPI to be run as root. This is usually strongly
# discouraged, but necessary to run Open MPI inside a container. For further
# details, see https://www.open-mpi.org/doc/v4.1/man1/mpirun.1.php#toc25.
MPI_ALLOW = "--allow-run-as-root"
MPI_DISTRIBUTION_FILENAME = "machinefile"


class MPIExecuter(executers.BaseExecuter):
    """Implementation of a general MPI Executer."""

    def __init__(
        self,
        working_dir,
        container_image,
        mpi_config: mpi_configuration.MPIClusterConfiguration,
        loki_logger: loki.LokiLogger,
        command_event_logger: executers.CommandEventLogger,
        sim_binary,
        file_type,
        sim_specific_input_filename,
    ):
        super().__init__(working_dir, container_image, mpi_config, loki_logger,
                         command_event_logger)
        self.sim_binary = sim_binary
        self.sim_specific_input_filename = sim_specific_input_filename
        self.file_type = file_type

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

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        use_hwthread = bool(self.args.use_hwthread)

        if use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])
        # Renaming input file as the simulator expects it to be
        os.rename(input_file_full_path,
                  os.path.join(sim_dir, self.sim_specific_input_filename))

        cmd = executers.Command(self.sim_binary + " " +
                                self.sim_specific_input_filename,
                                is_mpi=True)
        self.run_subprocess(cmd, working_dir=sim_dir)

        shutil.copytree(sim_dir, self.artifacts_dir, dirs_exist_ok=True)
