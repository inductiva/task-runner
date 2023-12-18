"""Utils to create the holes."""

from abc import ABC, abstractmethod
from typing import Tuple

import gmsh
import math


class Hole(ABC):
    """Abstract base class for holes.

    Attributes:
        center_x (float): x-coordinate of the center.
        center_y (float): y-coordinate of the center.
    """

    def __init__(self, center_x: float, center_y: float) -> None:
        """Initializes a Hole object."""
        self.center_x = center_x
        self.center_y = center_y

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "Hole":
        """Abstract method to create a Hole instance from a dictionary.

        Args:
            data (dict): A dictionary containing hole data.

        Returns:
            Hole: An instance of the Hole class or its subclasses.
        """
        pass

    @abstractmethod
    def perimeter(self):
        """Abstract method to calculate the perimeter of the hole."""
        pass

    @abstractmethod
    def to_dict(self):
        """Abstract method to convert the hole properties to a dictionary."""
        pass

    @abstractmethod
    def to_occ(self):
        """Abstract method to convert the hole to OpenCASCADE CAD."""
        pass

    @abstractmethod
    def get_hole_mesh_params(self):
        """Abstract method for hole mesh parameters."""
        pass


class CircularHole(Hole):
    """Circular hole.

    Attributes:
        radius (float): Hole radius.
    """

    def __init__(self, center_x: float, center_y: float, radius: float) -> None:
        """Initializes a CircularHole object."""
        super().__init__(center_x, center_y)
        self.radius = radius

    @classmethod
    def from_dict(cls, data: dict) -> "CircularHole":
        """Create a CircularHole instance from a dictionary.

        Args:
            data (dict): A dictionary containing circular hole data.

        Returns:
            CircularHole: An instance of the CircularHole class.
        """
        return cls(center_x=data.get("center_x"),
                   center_y=data.get("center_y"),
                   radius=data.get("radius"))

    def perimeter(self) -> float:
        """Calculate the perimeter of the hole.

        Returns:
            float: The calculated perimeter.
        """
        return 2 * math.pi * self.radius

    def to_dict(self) -> dict:
        """Convert hole properties to a dictionary.

        Returns:
            dict: Hole properties.
        """
        return {
            "hole_type": "circular",
            "center_x": self.center_x,
            "center_y": self.center_y,
            "radius": self.radius
        }

    def to_occ(self) -> int:
        """Converts hole to OpenCASCADE CAD representation.

        Returns:
          hole_gmsh (int): The Gmsh entity ID representing the hole's
            OpenCASCADE CAD representation.
        """
        hole_gmsh = gmsh.model.occ.addDisk(xc=self.center_x,
                                           yc=self.center_y,
                                           zc=0,
                                           rx=self.radius,
                                           ry=self.radius)
        return hole_gmsh

    def get_hole_mesh_params(self) -> Tuple[float, float]:
        """Gets the mesh generation parameters for the hole.

        Metrics:
          - mesh_offset (float): Represents an offset for the boundaries of the
            holes, defining a region around the boundaries. Within this region,
            we have the ability to control the mesh elements size.
            The offset is equal to the radius.
          - predefined_element_size (float): Represents the predefined element
            size, defined as the diameter.

        Returns:
            Tuple[float, float]: The mesh offset and the predefined element mesh
              size for the hole.
        """
        mesh_offset = self.radius
        predefined_element_size = self.radius * 2

        return mesh_offset, predefined_element_size


class RectangularHole(Hole):
    """Rectangular hole.

    Attributes:
        half_size_x (float): Half size of the hole in the x-direction.
        half_size_y (float): Half size of the hole in the y-direction.
        angle (float): Positive angle of rotation in degrees around the hole
          center.
    """

    def __init__(self, center_x: float, center_y: float, half_size_x: float,
                 half_size_y: float, angle: float) -> None:
        """Initializes a RectangularHole object."""
        super().__init__(center_x, center_y)
        self.half_size_x = half_size_x
        self.half_size_y = half_size_y
        self.angle = angle

    @classmethod
    def from_dict(cls, data: dict) -> "RectangularHole":
        """Create a RectangularHole instance from a dictionary.

        Args:
            data (dict): A dictionary containing rectangular hole data.

        Returns:
            RectangularHole: An instance of the RectangularHole class.
        """
        return cls(center_x=data.get("center_x"),
                   center_y=data.get("center_y"),
                   half_size_x=data.get("half_size_x"),
                   half_size_y=data.get("half_size_y"),
                   angle=data.get("angle"))

    def perimeter(self) -> float:
        """Calculate the perimeter of the hole.

        Returns:
            float: The calculated perimeter.
        """
        return self.half_size_x * 4 + self.half_size_y * 4

    def to_dict(self) -> dict:
        """Convert hole properties to a dictionary.

        Returns:
            dict: Hole properties.
        """
        return {
            "hole_type": "rectangular",
            "center_x": self.center_x,
            "center_y": self.center_y,
            "half_size_x": self.half_size_x,
            "half_size_y": self.half_size_y,
            "angle": self.angle
        }

    def to_occ(self) -> int:
        """Converts hole to OpenCASCADE CAD representation.

        To prevent singularity points in the Finite Element Method (points i
        the model where values tend towards infinity), we will round the corners
        of the rectangle.

        Returns:
            hole_gmsh (int): The Gmsh entity ID representing the hole's
              OpenCASCADE CAD representation.
        """
        hole_gmsh = gmsh.model.occ.addRectangle(
            x=self.center_x - self.half_size_x,
            y=self.center_y - self.half_size_y,
            z=0,
            dx=self.half_size_x * 2,
            dy=self.half_size_y * 2,
            roundedRadius=min(self.half_size_x, self.half_size_y) * 0.5)
        gmsh.model.occ.rotate(dimTags=[(2, hole_gmsh)],
                              x=self.center_x,
                              y=self.center_y,
                              z=0,
                              ax=0,
                              ay=0,
                              az=1,
                              angle=math.radians(self.angle))
        return hole_gmsh

    def get_hole_mesh_params(self) -> Tuple[float, float]:
        """Gets the mesh generation parameters for the hole.

        Metrics:
          - mesh_offset (float): Represents an offset for the boundaries of the
            holes, defining a region around the boundaries. Within this region,
            we have the ability to control the mesh elements size.
            The offset is equal to the the averages of the half-size values in
            both the x and y directions
          - predefined_element_size (float): Represents the predefined element
            size, defined as the total of the half-size values in
            both the x and y directions

        Returns:
            Tuple[float, float]: The mesh offset and the predefined element mesh
              size for the hole.
        """
        mesh_offset = (self.half_size_x + self.half_size_y) / 2
        predefined_element_size = self.half_size_x + self.half_size_y

        return mesh_offset, predefined_element_size


class EllipticalHole(Hole):
    """Elliptical hole.

    Attributes:
        semi_axis_x (float): The semi-axis along the x-direction.
        semi_axis_y (float): The semi-axis along the y-direction.
        angle (float): Positive angle of rotation in degrees around the hole
          center.
    """

    def __init__(self, center_x: float, center_y: float, semi_axis_x: float,
                 semi_axis_y: float, angle: float) -> None:
        """Initializes a EllipticalHole object."""
        super().__init__(center_x, center_y)
        self.semi_axis_x = semi_axis_x
        self.semi_axis_y = semi_axis_y
        self.angle = angle

    @classmethod
    def from_dict(cls, data: dict) -> "EllipticalHole":
        """Create an EllipticalHole instance from a dictionary.

        Args:
            data (dict): A dictionary containing elliptical hole data.

        Returns:
            EllipticalHole: An instance of the EllipticalHole class.
        """
        return cls(center_x=data.get("center_x"),
                   center_y=data.get("center_y"),
                   semi_axis_x=data.get("semi_axis_x"),
                   semi_axis_y=data.get("semi_axis_y"),
                   angle=data.get("angle"))

    def perimeter(self) -> float:
        """Calculate the perimeter of the hole.

        Returns:
            float: The calculated perimeter.
        """
        return math.pi * (3 * (self.semi_axis_x + self.semi_axis_y) - math.sqrt(
            (3 * self.semi_axis_x + self.semi_axis_y) *
            (self.semi_axis_x + 3 * self.semi_axis_y)))

    def to_dict(self) -> dict:
        """Convert hole properties to a dictionary.

        Returns:
            dict: Hole properties.
        """

        return {
            "hole_type": "elliptical",
            "center_x": self.center_x,
            "center_y": self.center_y,
            "semi_axis_x": self.semi_axis_x,
            "semi_axis_y": self.semi_axis_y,
            "angle": self.angle
        }

    def to_occ(self) -> int:
        """Converts hole to OpenCASCADE CAD representation.

        Gmsh adheres to a standard where it expects the major axis
        (larger semi-axis) of an ellipse or disk to be oriented parallel to the
        X-axis, while the minor axis (smaller semi-axis) should align with the
        Y-axis.

        When the length of the semi-axis along the X-axis is less than the
        length of the semi-axis along the Y-axis, the code swaps the major and
        minor semi-axis values. This adjustment ensures that the shape aligns
        correctly with Gmsh's convention. Furthermore, a 90-degree rotation is
        applied to ensure the shape is properly oriented.

        Returns:
            hole_gmsh (int): The Gmsh entity ID representing the hole's
              OpenCASCADE CAD representation.
        """
        rx, ry = self.semi_axis_x, self.semi_axis_y
        angle = self.angle

        if self.semi_axis_x < self.semi_axis_y:
            rx, ry = self.semi_axis_y, self.semi_axis_x
            angle += 90

        hole_gmsh = gmsh.model.occ.addDisk(xc=self.center_x,
                                           yc=self.center_y,
                                           zc=0,
                                           rx=rx,
                                           ry=ry)
        gmsh.model.occ.rotate(dimTags=[(2, hole_gmsh)],
                              x=self.center_x,
                              y=self.center_y,
                              z=0,
                              ax=0,
                              ay=0,
                              az=1,
                              angle=math.radians(angle))

        return hole_gmsh

    def get_hole_mesh_params(self) -> Tuple[float, float]:
        """Gets the mesh generation parameters for the hole.

        Metrics:
          - mesh_offset (float): Represents an offset for the boundaries of the
            holes, defining a region around the boundaries. Within this region,
            we have the ability to control the mesh elements size.
            The offset is equal to the the averages of the semi-axis values.
          - predefined_element_size (float): Represents the predefined element
            size, defined as the total of the semi-axis values.

        Returns:
            Tuple[float, float]: The mesh offset and the predefined element mesh
              size for the hole.
        """
        mesh_offset = (self.semi_axis_x + self.semi_axis_y) / 2
        predefined_element_size = self.semi_axis_x + self.semi_axis_y

        return mesh_offset, predefined_element_size
