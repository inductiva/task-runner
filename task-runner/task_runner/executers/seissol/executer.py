from task_runner.executers import ExecCommandLogger, MPIExecuter, mpi_configuration
from task_runner.utils import loki


class SeisSolExecuter(MPIExecuter):
    def __init__(
        self,
        working_dir,
        container_image,
        mpi_config: mpi_configuration.MPIClusterConfiguration,
        loki_logger: loki.LokiLogger,
        exec_command_logger: ExecCommandLogger,
    ):
        """
        Initialize the SeisSolExecuter.

        Args:
            working_dir (str): Working directory for the simulation.
            container_image (str): Container image to use for the simulation.
            mpi_config (MPIClusterConfiguration): MPI configuration details.
            loki_logger (LokiLogger): Logger for structured logs.
            exec_command_logger (ExecCommandLogger): Logger for command outputs.
        """
        super().__init__(
            working_dir=working_dir,
            container_image=container_image,
            loki_logger=loki_logger,
            exec_command_logger=exec_command_logger,
            mpi_config=mpi_config,
            sim_binary="SeisSol_Release_dhsw_4_elastic",
            file_type="par",
            sim_specific_input_filename="parameters.par",
        )
