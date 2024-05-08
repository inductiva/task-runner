"""Run simulation with Amr-Wind."""
from executer_tracker import executers
from executer_tracker.executers import mpi_configuration
from executer_tracker.utils import loki


class AmrWindExecuter(executers.MPIExecuter):

    def __init__(
        self,
        working_dir,
        container_image,
        mpi_config: mpi_configuration.MPIConfiguration,
        loki_logger: loki.LokiLogger,
    ):
        super().__init__(working_dir=working_dir,
                         container_image=container_image,
                         loki_logger=loki_logger,
                         mpi_config=mpi_config,
                         sim_binary="amr_wind",
                         file_type="inp",
                         sim_specific_input_filename="input.inp")
