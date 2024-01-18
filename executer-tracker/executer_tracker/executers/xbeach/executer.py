"""Run simulation with xBeach."""
from executer_tracker import executers
from executer_tracker.executers import mpi_configuration
from executer_tracker.utils import loki


class XBeachExecuter(executers.MPIExecuter):

    def __init__(
        self,
        working_dir,
        container_image,
        loki_logger: loki.LokiLogger,
        mpi_config: mpi_configuration.MPIConfiguration,
    ):
        super().__init__(working_dir=working_dir,
                         container_image=container_image,
                         loki_logger=loki_logger,
                         mpi_config=mpi_config,
                         sim_binary="xbeach",
                         file_type="txt",
                         sim_specific_input_filename="params.txt")
