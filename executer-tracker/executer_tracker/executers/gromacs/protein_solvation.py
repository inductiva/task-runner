"""Run ProteinSolvation Simulation with GROMACS"""
import os
import numpy as np

from executer_tracker.executers import gromacs
from executer_tracker.executers.gromacs import pre_processing, post_processing


class ProteinSolvationGROMACS(gromacs.GROMACS):
    """ProteinSolvation GROMACS executer."""

    def pre_process(self, pdb_file="protein.pdb"):
        """Extracts protein chain from PDB file."""

        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        pdb_file = os.path.join(input_dir, pdb_file)
        pre_processing.protein_solvation_pre_process(pdb_file=pdb_file)

    def post_process(self):
        rmsf_values = post_processing.calculate_rmsf_trajectory(
            working_dir=self.artifacts_dir)
        np.save(os.path.join(self.artifacts_dir, "rmsf_values.npy"),
                rmsf_values)
