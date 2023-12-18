"""Generic LinearElasticityFEniCSx executer."""

import os

from executer_tracker import executers

MESH_FILENAME = "mesh.msh"


class LinearElasticityFEniCSxExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run FEniCSx."""

    def execute(self):

        sim_dir_path = os.path.join(self.working_dir, self.args.sim_dir)
        mesh_path = os.path.join(sim_dir_path, MESH_FILENAME)
        bcs_path = os.path.join(sim_dir_path, self.args.bcs_filename)
        material_path = os.path.join(sim_dir_path, self.args.material_filename)
        element_order = self.args.mesh_element_order
        results_dir = self.artifacts_dir

        cmd = executers.Command("python /scripts/elastic_case/elastic_case.py "
                                f"--mesh_path {mesh_path} "
                                f"--bcs_path {bcs_path} "
                                f"--material_path {material_path} "
                                f"--element_order {element_order} "
                                f"--results_dir {results_dir}")

        self.run_subprocess(cmd)
