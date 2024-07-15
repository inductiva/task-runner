"""Generic Fire simulation with FDS."""
import os
import shutil

from executer_tracker import executers


class NWChemExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run NWChem."""

    def execute(self):
        sim_dir = os.path.join(self.working_dir, self.args.sim_dir)
        input_filename = self.args.input_filename

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        if self.args.use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

        # Copy the input files to the artifacts directory
        shutil.copytree(sim_dir, self.artifacts_dir, dirs_exist_ok=True)

        nwchem_bin = "nwchem"

        cmd = executers.Command(f"{nwchem_bin} {input_filename}", is_mpi=True)
        self.run_subprocess(cmd, working_dir=self.artifacts_dir)
