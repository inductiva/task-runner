"""Generic Reef3D executer."""
import os
import shutil

from executer_tracker import executers

DIVEMESH_INPUT_FILE = "control.txt"
REEF3D_INPUT_FILE = "ctrl.txt"


class REEF3DExecuter(executers.BaseExecuter):
    """Concrete implementation of the Reef3D executer."""

    def execute(self):
        """Reef3D simulation execution."""
        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        sim_dir = os.path.join(self.working_dir, self.args.sim_dir)

        # Copy the input files to the artifacts directory
        shutil.copytree(sim_dir, self.artifacts_dir, dirs_exist_ok=True)

        #Run DIVEMesh command
        divemesh_bin = "/DIVEMesh/bin/DiveMESH"
        cmd = executers.Command(divemesh_bin)
        self.run_subprocess(cmd, working_dir=self.artifacts_dir)

        # Run REEF3D command
        reef3d_bin = "/REEF3D/bin/REEF3D"
        cmd = executers.Command(reef3d_bin, is_mpi=True)
        self.run_subprocess(cmd, working_dir=self.artifacts_dir)
