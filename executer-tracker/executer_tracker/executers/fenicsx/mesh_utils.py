""""Mesh utilities for the deformable plate scenario."""
from typing import Optional

import gmsh
import time
import json
import numpy as np

from executer_tracker.executers.fenicsx import gmsh_utils
from executer_tracker.executers.fenicsx.geometry import geometry_utils


class GmshMesh:
    """Gmsh mesh.

    Attributes:
        geometry: A geometry_utils.GeometricCase object.
        global_refinement_factor (float, optional): The refinement factor for
          global refinement of the mesh. A higher value results in a finer mesh
          overall, increasing the number of elements in the entire mesh, and
          leading to a more detailed representation of the geometry. Use this
          factor when you want to globally refine the mesh uniformly, without
          specific local focus.
        local_refinement_factor (float, optional): The refinement factor for
          local refinement of the mesh. This factor controls the local
          refinement level of the mesh and is typically used for refining
          specific regions or features of the mesh. A higher value for this
          factor indicates a finer mesh in the regions of interest, providing
          more detailed resolution around certain features. Use this factor when
          you want to focus on refining specific areas while keeping the rest of
          the mesh less refined.
        smoothing_parameter (float, optional): The smoothing parameter for mesh
          generation. It controls the amount of mesh smoothing applied to the
          generated mesh. Adjust this parameter for improved mesh quality.
        runtime (float): Mesh generation time in seconds, initialized to 0.0.
    """

    def __init__(self,
                 geometry: geometry_utils.GeometricCase,
                 global_refinement_factor: Optional[float] = 1.0,
                 local_refinement_factor: Optional[float] = 1.0,
                 smoothing_parameter: Optional[float] = 10.0) -> None:
        """Initializes a GmshMesh object."""
        self.geometry = geometry
        self.global_refinement_factor = global_refinement_factor
        self.local_refinement_factor = local_refinement_factor
        self.smoothing_parameter = smoothing_parameter
        self.runtime = 0.0

    def _create_mesh_with_gmsh(self) -> None:
        """Creates the mesh with Gmsh.

        To generate the mesh using Gmsh, we utilize mesh size fields: the
        "Distance" and "Threshold" fields. Use add_mesh_field_distance to add
        the distance mesh field and add_mesh_field_threshold for the threshold
        mesh field in Gmsh.

        To control the element size using distance and threshold mesh size
        fields in Gmsh, we need to follow these steps:

        1. Define the distance-based mesh size field

        2. Define the threshold-based mesh size field

        3. Combine the distance and threshold-based fields:
            - To apply both distance and threshold fields, you can use the field
            IDs of the previously defined fields and combine them using
            mathematical operations (e.g., "Min" or "Max").
            - Use gmsh.model.mesh.field.add("Min", combined_mesh_field_id) to
            add a combined field that uses the minimum element size from the
            distance and threshold fields.
            - Use gmsh.model.mesh.field.setNumbers(combined_mesh_field_id,
            "FieldsList", list_mesh_field_id) to set the list of mesh fields
            that will be combined in the newly created field with the
            identifier combined_mesh_field_id.

        4. Set the mesh field as the background mesh field:
            - Use gmsh.model.mesh.field.setAsBackgroundMesh(
            combined_mesh_field_id) to set the combined field as the
            background mesh field, which will be used during mesh generation.

        5. Generate the mesh:
            - Finally, use gmsh.model.mesh.generate(dim=2) to generate the 2D
            mesh based on the defined mesh size fields and other meshing
            options.

        We can define both the global mesh size and the local mesh size (around
        the holes).
        """

        # Initialize the Gmsh API
        gmsh.initialize()

        # Disable Gmsh terminal output
        gmsh.option.setNumber("General.Terminal", 0)

        # Add a new model and set it as the current model
        gmsh.model.add("model")

        # Generate the plate with holes and get the boundary IDs
        (plate_curves_id, holes_curve_id
        ) = self.geometry.plate_with_holes_to_occ_and_get_boundary_ids()

        # Get mesh parameters
        (plate_mesh_offset, plate_predefined_element_size, holes_mesh_offset,
         _) = self.geometry.get_mesh_params()

        # Add physical markers for the plate and holes
        gmsh.model.addPhysicalGroup(2, [1])

        # Calculate the maximum global mesh size
        global_mesh_size_max = (plate_predefined_element_size /
                                self.global_refinement_factor)

        mesh_field_id = 0
        mesh_field_threshol_id = []

        # Loop through plate boundaries to apply distance and threshold-based
        # mesh fields
        for id_plate_boundary in range(len(plate_curves_id)):

            mesh_field_id += 1
            gmsh_utils.add_mesh_field_distance(
                mesh_field_id, [plate_curves_id[id_plate_boundary]], 100)

            mesh_field_id += 1
            gmsh_utils.add_mesh_field_threshold(mesh_field_id,
                                                mesh_field_id - 1,
                                                global_mesh_size_max,
                                                global_mesh_size_max, 0,
                                                plate_mesh_offset)
            mesh_field_threshol_id.append(mesh_field_id)

        # Check if local refinement is required
        if self.local_refinement_factor > 1.0:

            # Loop through holes to apply distance and threshold-based mesh
            # fields
            for id_hole in range(len(holes_curve_id)):

                # Calculate the local mesh size
                local_mesh_size = (global_mesh_size_max /
                                   self.local_refinement_factor)

                # Loop throught curves for each hole
                for hole_curve_id in holes_curve_id[id_hole]:

                    # Set the number of points to use along the hole's curve
                    # (100 for lines, 400 for other types)
                    if gmsh.model.getType(1, hole_curve_id) == "Line":
                        number_points = 100
                    else:
                        number_points = 400

                    mesh_field_id += 1
                    gmsh_utils.add_mesh_field_distance(mesh_field_id,
                                                       [hole_curve_id],
                                                       number_points)

                    mesh_field_id += 1
                    gmsh_utils.add_mesh_field_threshold(
                        mesh_field_id, mesh_field_id - 1, local_mesh_size,
                        global_mesh_size_max, 0, holes_mesh_offset[id_hole])
                    mesh_field_threshol_id.append(mesh_field_id)

        # Combine the distance and threshold-based fields
        combined_mesh_field_id = mesh_field_id + 1
        gmsh.model.mesh.field.add("Min", combined_mesh_field_id)
        gmsh.model.mesh.field.setNumbers(combined_mesh_field_id, "FieldsList",
                                         mesh_field_threshol_id)

        # Set the mesh field as the background mesh field
        gmsh.model.mesh.field.setAsBackgroundMesh(combined_mesh_field_id)

        # Set the meshing algorithm: Quasi-structured Quad method
        gmsh.option.setNumber("Mesh.Algorithm", 11)

        # Set mesh smoothing to improve mesh quality
        gmsh.option.set_number("Mesh.Smoothing", self.smoothing_parameter)

        # Generate the mesh in 2D
        start_time = time.time()
        gmsh.model.mesh.generate(dim=2)
        end_time = time.time()
        self.runtime = np.round(end_time - start_time, 2)

    def write_to_msh(self, msh_path: str) -> None:
        """Writes the GMSH mesh to MSH file.

        Args:
            msh_path (str): The mesh file path in MSH format.
        """
        self._create_mesh_with_gmsh()

        gmsh.write(msh_path)
        gmsh.finalize()

    def write_mesh_info_to_json(self, json_path: str) -> None:
        """Write mesh information to a JSON file.

        Args:
            json_path (str): The mesh information file path in JSON format.
        """

        # Create a dictionary with mesh information
        mesh_info_dict = {
            "global mesh refinement factor": self.global_refinement_factor,
            "local mesh refinement factor": self.local_refinement_factor,
            "runtime (s)": self.runtime
        }

        # Write the mesh info to JSON file
        with open(json_path, "w", encoding="utf-8") as write_file:
            json.dump(mesh_info_dict, write_file, indent=4)
