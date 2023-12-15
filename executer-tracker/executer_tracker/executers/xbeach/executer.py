"""Run simulation with xBeach."""
from typing import Optional
from executer_tracker import executers
from executer_tracker.executers import mpi_configuration


class XBeachExecuter(executers.MPIExecuter):

    def __init__(
        self,
        working_dir,
        container_image,
        mpi_config: Optional[mpi_configuration.MPIConfiguration],
    ):
        super().__init__(working_dir=working_dir,
                         container_image=container_image,
                         mpi_config=mpi_config,
                         sim_binary="xbeach",
                         file_type="txt",
                         sim_specific_input_filename="params.txt")
