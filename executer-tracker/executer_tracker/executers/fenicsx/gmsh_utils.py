"""Utils to create the mesh."""
from typing import List

import gmsh


def add_mesh_field_distance(mesh_field_id: int, curves_list: List[int],
                            num_points: int) -> None:
    """Add a distance-based mesh size field to control element size in Gmsh.

    - Use gmsh.model.mesh.field.add("Distance", mesh_field_id) to add a
    distance-based mesh size field, where mesh_field_id is a unique identifier
    for the field.
    - Set the curves or points where you want to apply the distance-based field
    using gmsh.model.mesh.field.setNumbers(field_id, "CurvesList", curves_list)
    or gmsh.model.mesh.field.setNumbers(field_id, "PointsList", points_list).
    Adjust the points_list of the field (i.e., how many points to use along
    curves or points) with
    gmsh.model.mesh.field.setNumber(field_id, "Sampling", num_points).

    Args:
        mesh_field_id (int): A unique identifier for the distance-based
          mesh size field.
        curves_list (List[int]): List of curve IDs where the
          distance-based field will be applied.
        num_points (int): Number of points to use along curves to adjust
          the field size.
    """

    # Add a distance-based mesh size field using the given field ID
    gmsh.model.mesh.field.add("Distance", mesh_field_id)

    # Set the curves where the distance-based field will be applied
    gmsh.model.mesh.field.setNumbers(mesh_field_id, "CurvesList", curves_list)

    # Adjust the points_list of the field to control mesh size along
    # curves
    gmsh.model.mesh.field.setNumber(mesh_field_id, "Sampling", num_points)


def add_mesh_field_threshold(mesh_field_id: int, ref_mesh_field_id: int,
                             size_min: float, size_max: float, dist_min: float,
                             dist_max: float) -> None:
    """Add a threshold-based mesh size field to control element size in Gmsh.

    - Use gmsh.model.mesh.field.add("Threshold", mesh_field_id) to add a
    threshold-based mesh size field, where mesh_field_id is a unique identifier
    for the field.
    - Use gmsh.model.mesh.field.setNumber(mesh_field_id, "InField",
    ref_mesh_field_id): The "InField" option specifies that this new field will
    use the values from another existing field to compute its own values. In
    this case, it uses the same field with an identifier ref_mesh_field_id as a
    basis for computation. This means that the new field will be based on the
    values of another field with an identifier one less than the current
    mesh_field_id. The "InField" option is useful for creating hierarchical mesh
    size fields, where one field depends on another, allowing more control over
    mesh refinement strategies.
    - Set the size constraints for the elements using
    gmsh.model.mesh.field.setNumber(field_id, "SizeMin", size_min) and
    gmsh.model.mesh.field.setNumber(field_id, "SizeMax", size_max).
    - Set the distance constraints for the elements using
    gmsh.model.mesh.field.setNumber(field_id, "DistMin", dist_min) and
    gmsh.model.mesh.field.setNumber(field_id, "DistMax", dist_max).

    Args:
        mesh_field_id (int): A unique identifier for the threshold-based
          mesh size field.
        ref_mesh_field_id (int): The identifier of the existing mesh
          size field to base the new field on.
        size_min (float): Minimum size constraint for the elements.
        size_max (float): Maximum size constraint for the elements.
        dist_min (float): Minimum distance constraint for the elements.
        dist_max (float): Maximum distance constraint for the elements.
    """

    # Add a threshold-based mesh size field using the given field ID
    gmsh.model.mesh.field.add("Threshold", mesh_field_id)

    # Set the reference field that the new field will use to compute its
    #  values
    gmsh.model.mesh.field.setNumber(mesh_field_id, "InField", ref_mesh_field_id)

    # Set the size constraints for the elements.
    gmsh.model.mesh.field.setNumber(mesh_field_id, "SizeMin", size_min)
    gmsh.model.mesh.field.setNumber(mesh_field_id, "SizeMax", size_max)

    # Set the distance constraints for the elements
    gmsh.model.mesh.field.setNumber(mesh_field_id, "DistMin", dist_min)
    gmsh.model.mesh.field.setNumber(mesh_field_id, "DistMax", dist_max)
