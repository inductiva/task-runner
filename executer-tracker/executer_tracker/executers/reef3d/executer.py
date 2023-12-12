"""Generic Reef3D executer."""
import os
import shutil
import psutil

from executer_tracker import executers

DIVEMESH_INPUT_FILE = "control.txt"
REEF3D_INPUT_FILE = "ctrl.txt"


class REEF3DExecuter(executers.BaseExecuter):
    """Concrete implementation of the Reef3D executer."""

    def modify_ncores_at_input_files(self, n_cores):
        """Modify number of cores in input files.

        For Reef3D, the number of cores is set on both
        input files ["control.txt", "ctrl.txt"] in the
        same way, by the following line:
                        `M 10 {n_cores}`.

        Hence, we read the files and alter this number
        based on the number of physical cores in the
        machine.
        """

        input_files = [
            os.path.join(self.artifacts_dir, DIVEMESH_INPUT_FILE),
            os.path.join(self.artifacts_dir, REEF3D_INPUT_FILE)
        ]

        for inputfile in input_files:
            # Read each input file.
            with open(inputfile, "r", encoding="utf-8") as read_file:
                read_lines = read_file.readlines()

            # Modify the line that sets the number of cores in each.
            with open(inputfile, "w", encoding="utf-8") as write_file:
                for line in read_lines:
                    if line.startswith("M 10"):
                        line = f"M 10 {n_cores}\n"
                    write_file.write(line)

    def execute(self):
        """Reef3D simulation execution."""

        n_cores = psutil.cpu_count(logical=False)
        sim_dir = os.path.join(self.working_dir, self.args.sim_dir)

        # Copy the input files to the artifacts directory
        shutil.copytree(sim_dir, self.artifacts_dir, dirs_exist_ok=True)
        # Add n_cores to input files
        self.modify_ncores_at_input_files(n_cores)

        #Run DIVEMesh command
        divemesh_bin = "/DIVEMesh/bin/DiveMESH"
        cmd = executers.Command(divemesh_bin)
        self.run_subprocess(cmd, working_dir=self.artifacts_dir)

        # Run REEF3D command
        reef3d_bin = "/REEF3D/bin/REEF3D"
        cmd = executers.Command(f"mpirun -n {n_cores} {reef3d_bin}")
        self.run_subprocess(cmd, working_dir=self.artifacts_dir)
