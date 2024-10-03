"""Runs the `compute_magnetic_field` script."""
import os

from task_runner import executers


class SimsoptExecuter(executers.BaseExecuter):
    """Simsopt simulation.

    Simsopt is a framework for optimizing stellarators. The high-level routines
    of simsopt are in python, with calls to C++ or fortran, where needed, for
    performance. Provides several different components, from tools for defining
    different types of objectives functions, to be used in the optimization
    process, to tools for the creation of objects that are important in
    stellarator configurations, such as curves and surfaces, with an abundance
    of distinct parameterizations and even tools for parallelized finite
    difference gradient calculations.

    Here Simsopt is being used for the creation of a set of coils, given the
    coefficients that describe their Fourier Series representation and the
    currents that run through them, and the subsequent calculation of the
    magnetic field that they produce on a given surface, using an efficient
    implementation of the Biot-Savart law. It is also being used for the
    calculation of some functions that assess the performance of the
    stellarator. For more information about these function, check out the
    `objectives.py` file in the `utilities` folder.
    """

    def execute(self):
        sim_dir_path = os.path.join(self.working_dir, self.args.sim_dir)

        coil_coefficients_file_path = os.path.join(
            sim_dir_path, self.args.coil_coefficients_filename)
        coil_currents_file_path = os.path.join(sim_dir_path,
                                               self.args.coil_currents_filename)
        plasma_surface_file_path = os.path.join(
            sim_dir_path, self.args.plasma_surface_filename)

        objectives_weights_file_path = os.path.join(
            sim_dir_path, self.args.objectives_weights_filename)

        cmd = executers.Command(
            "python /scripts/stellarator_search.py "
            f"--coil_coefficients_file_path={coil_coefficients_file_path} "
            f"--coil_currents_file_path={coil_currents_file_path} "
            f"--plasma_surface_file_path={plasma_surface_file_path} "
            f"--num_field_periods={self.args.num_field_periods} "
            f"--num_samples={self.args.num_samples} "
            f"--num_iterations={self.args.num_iterations} "
            f"--sigma_scaling_factor={self.args.sigma_scaling_factor} "
            f"--objectives_weights_file_path={objectives_weights_file_path} "
            f"--output_path={self.output_dir}/artifacts/")
        self.run_subprocess(cmd)
