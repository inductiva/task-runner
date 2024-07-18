"""Run simulation with SWASH."""
from executer_tracker import executers
from executer_tracker.executers import mpi_configuration
from executer_tracker.utils import loki


class SWASHExecuter(executers.MPIExecuter):

    def __init__(
        self,
        working_dir,
        container_image,
        mpi_config: mpi_configuration.MPIClusterConfiguration,
        loki_logger: loki.LokiLogger,
    ):
        super().__init__(working_dir=working_dir,
                         container_image=container_image,
                         loki_logger=loki_logger,
                         mpi_config=mpi_config,
                         sim_binary="swash.exe",
                         file_type="sws",
                         sim_specific_input_filename="INPUT")
