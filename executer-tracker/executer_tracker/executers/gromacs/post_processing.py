"""Post processing tools for Gromacs MD simulations."""
import os

import MDAnalysis as mda
from MDAnalysis import transformations
from MDAnalysis.analysis import align


def unwrap_trajectory(topology_path, trajectory_path):
    """Unwrap visualization of the trajectory to deal with
    Periodic Boundary Conditions.
    Args:
        topology_path: Path to the topology file.
        trajectory_path: Path to the trajectory file."""
    universe = mda.Universe(topology_path, trajectory_path, guess_bonds=True)
    atoms = universe.atoms
    transformation = transformations.unwrap(atoms)
    universe.trajectory.add_transformations(transformation)
    return universe


def align_trajectory_to_average(universe, trajectory_output_path):
    """Align the trajectory to the average structure.
    Args:
        universe: The universe MDAnalysis object.
        trajectory_output_path: Path to the aligned trajectory file."""
    average = align.AverageStructure(universe,
                                     universe,
                                     select="protein and name CA",
                                     ref_frame=0).run()
    average_trajectory = average.results.universe

    align.AlignTraj(universe,
                    average_trajectory,
                    select="protein and name CA",
                    filename=trajectory_output_path,
                    in_memory=False).run()


def calculate_rmsf_trajectory(working_dir):
    """Calculate the root mean square fluctuation (RMSF) over a trajectory.

        It is typically calculated for the alpha carbon atom of each residue.
        These atoms make the backbone of the protein.The RMSF is the square root
        of the variance of the fluctuation around the average position:
        &rhoi = √⟨(xi - ⟨xi⟩)²⟩
        It quantifies how much a structure diverges from the average structure
        over time, the RSMF can reveal which areas of the system are the most
        mobile. Check
        https://userguide.mdanalysis.org/stable/examples/analysis/alignment_and_rms/rmsf.html
        for more details."""
    topology_path = os.path.join(working_dir, "solvated_protein.tpr")
    full_trajectory_path = os.path.join(working_dir, "full_trajectory.trr")
    full_precision_universe = mda.Universe(topology_path, full_trajectory_path)

    aligned_trajectory_path = os.path.join(working_dir, "aligned_traj.dcd")
    align_trajectory_to_average(full_precision_universe,
                                aligned_trajectory_path)
    align_universe = mda.Universe(topology_path, aligned_trajectory_path)

    # Calculate RMSF for carbon alpha atoms
    c_alphas = align_universe.select_atoms("protein and name CA")
    rmsf = mda.analysis.rms.RMSF(c_alphas).run()
    rmsf_values = rmsf.results.rmsf

    return rmsf_values
