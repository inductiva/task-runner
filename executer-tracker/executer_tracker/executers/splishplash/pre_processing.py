""""Pre-processing utilities for the fluid tank scenario."""

import gmsh_utils


def create_tank_mesh_file(tank_dict, obj_file_path):
    """Creates a mesh file for the tank.

    The tank is composed of two blocks:
    - a main (cylindrical/cubic) block representing the tank itself;
    - an optional smaller (cylindrical/cubic) block representing a fluid outlet.
      When present, the top base of this block connects with the bottom base of
      the tank, such that fluid flows freely from the tank to the outlet. The
      bottom base of the outlet is also open, such that flow exits the outlet.

    Both blocks are assumed to have their main axes aligned with the z
    axis.

    Args:
        shape: Shape of the tank.
        outlet: Shape of the outlet. If `None`, no outlet is present.
        path: Path of the file to be created.
    """

    with gmsh_utils.gmshAPIWrapper():
        tank_base_hole_loops = []

        tank_shape = tank_dict["shape"]
        outlet = tank_dict["outlet"]

        if outlet is not None:

            outlet_shape = outlet["shape"]

            # Add a circle arc/rectangle loop representing the top base of the
            # outlet. An arc/loop is used instead of a circle/rectangle because
            # this face is not filled, i.e. it is not a surface.
            if outlet_shape["type"] == "cylinder":
                p_top_outlet, c_top_outlet, l_top_outlet = \
                    gmsh_utils.add_circle_arc(
                        x=outlet_shape["position"][0],
                        y=outlet_shape["position"][1],
                        z=outlet_shape["position"][2] + outlet_shape["height"],
                        r=outlet_shape["radius"],
                    )
            elif outlet_shape["type"] == "cube":
                p_top_outlet, c_top_outlet, l_top_outlet = \
                    gmsh_utils.add_z_rectangle_loop(
                        x=outlet_shape["position"][0],
                        y=outlet_shape["position"][1],
                        z=outlet_shape["position"][2] + \
                          outlet_shape["dimensions"][2],
                        lx=outlet_shape["dimensions"][0],
                        ly=outlet_shape["dimensions"][1],
                    )

            # Add a circle arc/rectangle loop representing the bottom base of
            # the outlet.
            if outlet_shape["type"] == "cylinder":
                p_bottom_outlet, c_bottom_outlet, _ = gmsh_utils.add_circle_arc(
                    x=outlet_shape["position"][0],
                    y=outlet_shape["position"][1],
                    z=outlet_shape["position"][2],
                    r=outlet_shape["radius"],
                )
            elif outlet_shape["type"] == "cube":
                p_bottom_outlet, c_bottom_outlet, _ = \
                    gmsh_utils.add_z_rectangle_loop(
                        x=outlet_shape["position"][0],
                        y=outlet_shape["position"][1],
                        z=outlet_shape["position"][2],
                        lx=outlet_shape["dimensions"][0],
                        ly=outlet_shape["dimensions"][1],
                    )

            # Add the walls of the outlet (cylindrical/cubic) block.
            gmsh_utils.add_cylinder_walls(p_bottom_outlet, c_bottom_outlet,
                                          p_top_outlet, c_top_outlet)

            # Add the loop representing the top base of the outlet to the list
            # of loops representing holes in the bottom base of the tank
            # cylinder.
            tank_base_hole_loops.append(l_top_outlet)

        # Add the top and bottom bases of the tank block, setting the loop
        # representing the top base of the outlet as a hole.
        if tank_shape["type"] == "cylinder":
            p_top, c_top, _, _ = gmsh_utils.add_circle(
                x=tank_shape["position"][0],
                y=tank_shape["position"][1],
                z=tank_shape["position"][2] + tank_shape["height"],
                r=tank_shape["radius"],
                hole_loops=[],
            )
            p_bottom, c_bottom, _, _ = gmsh_utils.add_circle(
                x=tank_shape["position"][0],
                y=tank_shape["position"][1],
                z=tank_shape["position"][2],
                r=tank_shape["radius"],
                hole_loops=tank_base_hole_loops,
            )

        elif tank_shape["type"] == "cube":
            p_top, c_top, _, _ = gmsh_utils.add_z_rectangle(
                x=tank_shape["position"][0],
                y=tank_shape["position"][1],
                z=tank_shape["position"][2] + tank_shape["dimensions"][2],
                lx=tank_shape["dimensions"][0],
                ly=tank_shape["dimensions"][1],
                hole_loops=[],
            )
            p_bottom, c_bottom, _, _ = gmsh_utils.add_z_rectangle(
                x=tank_shape["position"][0],
                y=tank_shape["position"][1],
                z=tank_shape["position"][2],
                lx=tank_shape["dimensions"][0],
                ly=tank_shape["dimensions"][1],
                hole_loops=tank_base_hole_loops,
            )

        # Add the walls of the tank (cylindrical/cubic) block.
        gmsh_utils.add_cylinder_walls(p_bottom, c_bottom, p_top, c_top)

    # Convert the msh file generated by gmsh to obj format.
    gmsh_utils.convert_msh_to_obj_file(obj_file_path)


def create_tank_fluid_mesh_file(tank_dict, margin, obj_file_path):
    """Creates a mesh file for the fluid.

    The fluid is represented by a block with the same shape as the tank, but
    with a smaller height.

    Args:
        shape: Shape of the tank.
        fluid_level: Height of the fluid.
        margin: Margin to be added to the fluid block.
        path: Path of the file to be created.
    """

    tank_shape = tank_dict["shape"]

    if tank_shape["type"] == "cube":
        with gmsh_utils.gmshAPIWrapper():
            gmsh_utils.add_box(
                tank_shape["position"][0] + margin,
                tank_shape["position"][1] + margin,
                tank_shape["position"][2] + margin,
                tank_shape["dimensions"][0] - 2 * margin,
                tank_shape["dimensions"][1] - 2 * margin,
                tank_dict["fluid_level"] - 2 * margin,
            )

    elif tank_shape["type"] == "cylinder":
        with gmsh_utils.gmshAPIWrapper():
            gmsh_utils.add_cylinder(
                tank_shape["position"][0],
                tank_shape["position"][1],
                tank_shape["position"][2] + margin,
                tank_shape["radius"] - margin,
                tank_dict["fluid_level"] - margin,
            )
    else:
        raise ValueError(f"Invalid fluid shape `{tank_shape}`.")

    # Convert the msh file generated by gmsh to obj format.
    gmsh_utils.convert_msh_to_obj_file(obj_file_path)
