"""Generic SPlisHSPlasH executer."""

import os

from executers_common import BaseExecuter


class SPlisHSPlasHExecuter(BaseExecuter):
    """Concrete implementation of an Executer to run SPlisHSPlasH."""

    def execute(self):
        sph_input_dir = self.args.sim_dir
        sph_input_file = self.args.input_filename

        # TODO: Add support for machines with GPU
        device = "cpu"

        binary_env_varname = f"SPLISHSPLASH_BINARY_{device.upper()}"

        device_binary_path = os.getenv(binary_env_varname)

        if device_binary_path is None:
            raise OSError("SPlisHSPlasH binary not found."
                          "Set the environment variable "
                          f"'{binary_env_varname}' to point to it.")

        input_json_path = os.path.join(self.working_dir, sph_input_dir,
                                       sph_input_file)

        self.run_subprocess(f"{device_binary_path} {input_json_path} "
                            f"--output-dir {self.artifacts_dir} "
                            f"--no-gui")
