"""SPH simulation script for the fluid tank scenario."""

import json
import os

from absl import app, logging

import executer
import pre_processing

TANK_JSON_FILENAME = "tank.json"
TANK_MESH_FILENAME = "tank.obj"
FLUID_MESH_FILENAME = "fluid.obj"


class FluidTankSPlisHSPlasHExecuter(executer.SPlisHSPlasHExecuter):
    """Fluid tank SPlisHSPlasH executer."""

    def pre_process(self):
        """Produces mesh files for the fluid tank scenario."""

        with open(os.path.join(self.args.sim_dir, TANK_JSON_FILENAME),
                  mode="r",
                  encoding="utf-8") as json_file:
            tank_dict = json.load(json_file)

        pre_processing.create_tank_mesh_file(
            tank_dict=tank_dict,
            obj_file_path=os.path.join(self.args.sim_dir, TANK_MESH_FILENAME),
        )
        pre_processing.create_tank_fluid_mesh_file(
            tank_dict=tank_dict,
            margin=2 * self.args.particle_radius,
            obj_file_path=os.path.join(self.args.sim_dir, FLUID_MESH_FILENAME),
        )


def main(_):
    executer_instance = FluidTankSPlisHSPlasHExecuter()
    executer_instance.run()


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
