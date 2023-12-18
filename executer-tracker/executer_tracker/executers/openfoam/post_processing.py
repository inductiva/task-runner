"""Visualization processing of WindTunnel scenario.

This class implements various visualization capabilities for
the WindTunnel scenario. Namely:
    - Pressure over object;
    - Cutting plane;
    - StreamLines.

Currently, we only support the OpenFOAM simulator.
"""
import os
from dataclasses import dataclass
from enum import Enum
from typing import Literal
import csv
import pathlib

import pyvista as pv


def compute_default_slices(output, save_dir):
    """Compute vertical and horizontal slices of the flow."""

    _, object_mesh = output.get_output_mesh()
    object_height = object_mesh.bounds[5] - object_mesh.bounds[4]

    output.get_flow_slice(plane="xz",
                          origin=(0, 0, 0),
                          save_path=os.path.join(save_dir, "xz_flow_slice.vtk"))

    output.get_flow_slice(plane="yz",
                          origin=(0, 0, 0),
                          save_path=os.path.join(save_dir, "yz_flow_slice.vtk"))

    output.get_flow_slice(plane="xy",
                          origin=(0, 0, object_height / 2),
                          save_path=os.path.join(save_dir, "xy_flow_slice.vtk"))


def wind_tunnel_postprocessing(simulation_output_dir):
    """Compute post-processing default outputs for the WindTunnel.
    
    The default files provide the pressure_field, streamlines,
    flow_slice and force_coefficients at the last time step.

    The last time step is the second directory in the
    sorted list of directories inside the simulation outout directory.
    At the moment users will only obtain info about the last time
    step.
    """

    output = WindTunnelOutput(simulation_output_dir)

    output.get_object_physical_field("pressure",
                                     save_path=os.path.join(
                                         simulation_output_dir,
                                         "pressure_field.vtk"))
    output.get_streamlines(
        save_path=os.path.join(simulation_output_dir, "streamlines.vtk"))
    output.get_force_coefficients(
        save_path=os.path.join(simulation_output_dir, "force_coefficients.csv"))
    compute_default_slices(output, save_dir=simulation_output_dir)


class WindTunnelOutput:
    """Post-Process WindTunnel simulation outputs.

    This class contains several methods to post-process the output 
    and visualize the results of a WindTunnel simulation.

    Current Support:
        OpenFOAM
    """

    def __init__(self, sim_output_path: str):
        """Initializes a `WindTunnelSimulationOutput` object.

        Args:
            sim_output_path: Path to simulation output files.
        """

        self.sim_output_path = sim_output_path
        outputs_dir_list = sorted(os.listdir(sim_output_path))
        self.last_time_step = float(outputs_dir_list[1])

    def get_output_mesh(self):  # pylint: disable=unused-argument
        """Get domain and object mesh info after WindTunnel simulation.

        Current Support - OpenFOAM
        """

        # The OpenFOAM data reader from PyVista requires that a file named
        # "foam.foam" exists in the simulation output directory.
        # Create this file if it does not exist.
        foam_file_path = os.path.join(self.sim_output_path, "foam.foam")
        pathlib.Path(foam_file_path).touch(exist_ok=True)

        reader = pv.OpenFOAMReader(foam_file_path)
        reader.set_active_time_value(self.last_time_step)

        full_mesh = reader.read()
        domain_mesh = full_mesh["internalMesh"]
        object_mesh = full_mesh["boundary"]["object"]

        return domain_mesh, object_mesh

    def get_object_physical_field(self,
                                  physical_field: str = "pressure",
                                  save_path: str = "pressure_field.vtk"):
        """Get a physical scalar field over mesh points.

        Args:
            physical_field: Physical property to be read.
            save_path: Path to save the physical field over the mesh.
        """

        _, object_mesh = self.get_output_mesh()

        field_name = OpenFOAMPhysicalField[physical_field.upper()].value

        self.mesh = pv.PolyData(object_mesh.points, faces=object_mesh.faces)
        self.mesh.point_data[field_name] = object_mesh.point_data[field_name]
        self.mesh.cell_data[field_name] = object_mesh.cell_data[field_name]
        self.mesh.save(save_path)

    def get_streamlines(self,
                        max_time: float = 100,
                        n_points: int = 100,
                        initial_step_length: float = 1,
                        source_radius: float = 0.7,
                        save_path: str = "streamlines.vtk"):
        """Get streamlines through the fluid/domain in the WindTunnel.
        
        The streamlines are obtained by seeding a set of points
        at the inlet of the WindTunnel.

        Args:
            max_time: Time used for integration of the streamlines.
                Not related with simulation time.
            n_points: Number of points to seed.
            initial_step_length: Initial step length for the streamlines.
            source_radius: Radius of the source of the streamlines.
            save_path: Path to save the streamlines. 
                Types of files permitted: .vtk, .ply, .stl
        """

        mesh, _ = self.get_output_mesh()

        inlet_position = (mesh.bounds[0], 0, 1)

        streamlines_mesh = mesh.streamlines(
            max_time=max_time,
            n_points=n_points,
            initial_step_length=initial_step_length,
            source_radius=source_radius,
            source_center=inlet_position)

        streamlines_mesh.save(save_path)

    def get_flow_slice(self,
                       plane: Literal["xy", "xz", "yz"] = "xz",
                       origin: tuple = (0, 0, 0),
                       save_path: str = "flow_slice.vtk"):
        """Get flow properties in a slice of the domain in WindTunnel.
        
        Args:
            plane: Orientation of the plane to slice the domain.
            origin: Origin of the plane.
            save_path: Path to save the flow slice. 
                Types of files permitted: .vtk, .ply, .stl
        """

        mesh, _ = self.get_output_mesh()

        if plane == "xy":
            normal = (0, 0, 1)
        elif plane == "yz":
            normal = (1, 0, 0)
        elif plane == "xz":
            normal = (0, 1, 0)
        else:
            raise ValueError("Invalid view.")

        flow_slice = mesh.slice(normal=normal, origin=origin)
        flow_slice.save(save_path)

    def get_force_coefficients(self, save_path: str = "force_coefficients.csv"):
        """Get the force coefficients of the object in the WindTunnel.
        
        The force coefficients are provided in a .dat file during the
        simulation run-time. This file contains 8 lines that are provide
        the general input information. In this function, we read the file,
        ignore the first 8 lines and read the force coefficients for the 
        simulation_time chosen.

        Args:
            save_path: Path to save the force coefficients in a .csv file.
        """

        num_header_lines = 8
        force_coefficients_path = os.path.join(self.sim_output_path,
                                               "postProcessing", "forceCoeffs1",
                                               "0", "forceCoeffs.dat")
        force_coefficients = []

        with open(force_coefficients_path, "r",
                  encoding="utf-8") as forces_file:
            for index, line in enumerate(forces_file.readlines()):
                # Pick the line 8 of the file:
                # [#, Time, Cm, Cd, Cl, Cl(f), Cl(r)] and remove the # column
                if index == num_header_lines:
                    force_coefficients.append(line.split()[1:])
                # Add the force coefficients for the simulation time chosen
                elif index == num_header_lines + self.last_time_step + 1:
                    force_coefficients.append(line.split())

        if save_path:
            with open(save_path, "w", encoding="utf-8") as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerows(force_coefficients)

        return force_coefficients


@dataclass
class OpenFOAMPhysicalField(Enum):
    """Defines the notation used for physical field in OpenFOAM."""
    PRESSURE = "p"
    VELOCITY = "U"
