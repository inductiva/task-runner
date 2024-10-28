"""Run simulation with Amr-Wind."""
from task_runner import executers
from task_runner.executers import mpi_configuration
from task_runner.utils import loki


class AmrWindExecuter(executers.MPIExecuter):

    def __init__(
        self,
        working_dir,
        container_image,
        mpi_config: mpi_configuration.MPIClusterConfiguration,
        loki_logger: loki.LokiLogger,
        command_event_logger: executers.CommandEventLogger,
    ):
        super().__init__(working_dir=working_dir,
                         container_image=container_image,
                         loki_logger=loki_logger,
                         command_event_logger=command_event_logger,
                         mpi_config=mpi_config,
                         sim_binary="amr_wind",
                         file_type="inp",
                         sim_specific_input_filename="input.inp")
