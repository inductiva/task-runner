"""Generic Fire simulation with FDS."""
from task_runner import executers
from task_runner.executers import mpi_configuration
from task_runner.utils import loki


class NWChemExecuter(executers.MPIExecuter):
    """Concrete implementation of an Executer to run NWChem."""

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
                         sim_binary="nwchem",
                         file_type="nw",
                         sim_specific_input_filename="input.nw")
