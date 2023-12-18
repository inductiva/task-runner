"""Run simulation with xBeach."""
from executer_tracker import executers


class XBeachExecuter(executers.MPIExecuter):

    def __init__(self, working_dir, container_image):
        super().__init__(working_dir=working_dir,
                         container_image=container_image,
                         sim_binary="xbeach",
                         file_type="txt",
                         sim_specific_input_filename="params.txt")
