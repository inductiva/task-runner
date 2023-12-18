"""Run simulation with SWASH."""
from executer_tracker import executers


class SWASHExecuter(executers.MPIExecuter):

    def __init__(self, working_dir, container_image):
        super().__init__(working_dir=working_dir,
                         container_image=container_image,
                         sim_binary="swash.exe",
                         file_type="sws",
                         sim_specific_input_filename="INPUT")
