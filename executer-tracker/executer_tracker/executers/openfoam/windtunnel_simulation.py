"""Simulation script for the WindTunnel with OpenFOAM."""
from executer_tracker.executers import openfoam
from executer_tracker.executers.openfoam import post_processing


class WindTunnelOpenFOAMExecuter(openfoam.OpenFOAMExecuter):
    """WindTunnel OpenFOAM executer."""

    def post_process(self):
        """Computes default output simulation files WindTunnel style.

        The default files provide the pressure_field, streamlines,
        flow_slice and force_coefficients at the last time step.
        """

        post_processing.wind_tunnel_postprocessing(
            simulation_output_dir=self.artifacts_dir)
