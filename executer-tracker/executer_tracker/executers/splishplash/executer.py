"""Generic SPlisHSPlasH executer."""

import os
import shutil

from executer_tracker import executers


class SPlisHSPlasHExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run SPlisHSPlasH."""

    def execute(self):
        sph_input_file = self.args.input_filename
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        device = "cpu"

        binary_path_map = {
            "cpu": "/SPlisHSPlasH_CPU/bin/SPHSimulator",
            "gpu": "/SPlisHSPlasH_GPU/bin/SPHSimulator",
        }
        binary_path = binary_path_map[device]

        input_json_path = os.path.join(self.artifacts_dir, sph_input_file)

        cmd = executers.Command(f"{binary_path} {input_json_path} "
                                f"--output-dir {self.artifacts_dir} "
                                f"--no-gui")

        self.run_subprocess(cmd)
