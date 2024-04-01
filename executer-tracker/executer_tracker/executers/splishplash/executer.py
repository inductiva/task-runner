"""Generic SPlisHSPlasH executer."""

import os

from executer_tracker import executers


class SPlisHSPlasHExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run SPlisHSPlasH."""

    def execute(self):
        sph_input_dir = self.args.sim_dir
        sph_input_file = self.args.input_filename

        device = "cpu"

        binary_path_map = {
            "cpu": "/SPlisHSPlasH_CPU/bin/SPHSimulator",
            "gpu": "/SPlisHSPlasH_GPU/bin/SPHSimulator",
        }
        binary_path = binary_path_map[device]

        input_json_path = os.path.join(self.working_dir, sph_input_dir,
                                       sph_input_file)

        cmd = executers.Command(f"{binary_path} {input_json_path} "
                                f"--output-dir {self.artifacts_dir} "
                                f"--no-gui")
    
        self.run_subprocess(cmd)
