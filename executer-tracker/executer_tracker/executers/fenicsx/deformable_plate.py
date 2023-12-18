"""FEM simulation for the deformable plate scenario in linear elasticity."""
import os
import shutil

from executer_tracker.executers import fenicsx
from executer_tracker.executers.fenicsx import mesh_utils
from executer_tracker.executers.fenicsx.geometry import geometry_utils

MESH_FILENAME = "mesh.msh"
MESH_INFO_FILENAME = "mesh_info.json"


class DeformablePlateLinearElasticityFEniCSxExecuter(
        fenicsx.LinearElasticityFEniCSxExecuter):
    """Deformable plate linear elasticity FEniCSx executer."""

    def pre_process(self):
        """Produces mesh file for the deformable plate scenario."""

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
