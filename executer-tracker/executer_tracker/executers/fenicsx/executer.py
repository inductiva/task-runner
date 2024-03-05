"""Generic LinearElasticityFEniCSx executer."""

import os
import shutil

from executer_tracker import executers
from executer_tracker.executers.fenicsx import mesh_utils
from executer_tracker.executers.fenicsx.geometry import geometry_utils

MESH_FILENAME = "mesh.msh"
MESH_INFO_FILENAME = "mesh_info.json"


class LinearElasticityFEniCSxExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run FEniCSx."""

    def pre_process(self):
        sim_dir_path = os.path.join(self.working_dir, self.args.sim_dir)

        # Geometry file
        geometry_path = os.path.join(sim_dir_path, self.args.geometry_filename)
        geometry = geometry_utils.GeometricCase.from_json(geometry_path)
        shutil.copy(geometry_path, self.artifacts_dir)

        # Mesh file
        mesh_path = os.path.join(sim_dir_path, MESH_FILENAME)
        mesh = mesh_utils.GmshMesh(
            geometry=geometry,
            global_refinement_factor=self.args.global_refinement_meshing_factor,
            local_refinement_factor=self.args.local_refinement_meshing_factor,
            smoothing_parameter=self.args.smoothing_meshing_parameter)
        mesh.write_to_msh(mesh_path)

        # Mesh information file
        mesh_info_path = os.path.join(self.artifacts_dir, MESH_INFO_FILENAME)
        mesh.write_mesh_info_to_json(mesh_info_path)

    def execute(self):
        sim_dir_path = os.path.join(self.working_dir, self.args.sim_dir)
        mesh_path = os.path.join(sim_dir_path, MESH_FILENAME)
        bcs_path = os.path.join(sim_dir_path, self.args.bcs_filename)
        material_path = os.path.join(sim_dir_path, self.args.material_filename)
        element_family = self.args.mesh_element_family
        element_order = self.args.mesh_element_order
        quadrature_rule=self.args.mesh_quadrature_rule
        quadrature_degree=self.args.mesh_quadrature_degree
        results_dir = self.artifacts_dir

        cmd = executers.Command("python /scripts/elastic_case/elastic_case.py "
                                f"--mesh_path {mesh_path} "
                                f"--bcs_path {bcs_path} "
                                f"--material_path {material_path} "
                                f"--element_family {element_family} "
                                f"--element_order {element_order} "
                                f"--quadrature_rule {quadrature_rule} "
                                f"--quadrature_degree {quadrature_degree} "
                                f"--results_dir {results_dir}")

        self.run_subprocess(cmd)
