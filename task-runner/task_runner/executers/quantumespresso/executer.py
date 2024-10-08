"""Executer tracker for QuantumEspresso"""
import os
import shutil

from task_runner import executers


class QuantumEspressoCommand(executers.Command):
    """QuantumEspresso command."""

    ALLOWED_COMMANDS_PREFIX = [
        "alpha2f", "dvscf_q2r", "head", "matdyn", "plan_avg", "pw", "rism1d",
        "turbo_spectrum", "average", "dynmat", "hp", "molecularnexafs",
        "plotband", "pw2bgw", "scan_ibrav", "upfconv", "band_interpolation",
        "epa", "ibrav2cell", "molecularpdos", "plotproj", "pw2critic", "simple",
        "virtual_v2", "bands", "epsilon", "initial_state", "neb", "plotrho",
        "pw2gt", "simple_bse", "wannier90", "bse_main", "ev", "kcw",
        "open_grid", "pmw", "pw2gw", "simple_ip", "wannier_ham", "casino2upf",
        "fermi_proj", "kcwpp_interp", "oscdft_et", "postahc", "pw2wannier90",
        "spectra_correction", "wannier_plot", "cell2ibrav", "fermi_velocity",
        "kcwpp_sh", "oscdft_pp", "postw90", "pw4gww", "sumpdos", "wfck2r", "cp",
        "fqha", "kpoints", "path_interpolation", "pp", "pwcond",
        "turbo_davidson", "wfdd", "cppp", "fs", "lambda", "pawplot", "ppacf",
        "pwi2xsf", "turbo_eels", "xspectra", "d3hess", "gww", "ld1", "ph",
        "pprism", "q2qstar", "turbo_lanczos", "dos", "gww_fit", "manycp",
        "phcg", "projwfc", "q2r", "turbo_magnon"
    ]

    # Some commands from the mpi build do not support mpi
    MPI_DISABLED = [
        "fqha.x", "molecularnexafs.x", "oscdft_et.x", "oscdft_pp.x",
        "plotproj.x", "plotrho.x", "postw90.x", "sumpdos.x", "wannier90.x",
        "wfdd.x"
    ]

    def _check_security(self, tokens, prompts):
        super()._check_security(tokens, prompts)

        if not any(self.args[0].startswith(s)
                   for s in self.ALLOWED_COMMANDS_PREFIX):
            raise ValueError("The command must start with one of the Quantum "
                             "Espresso binaries.")


class QuantumEspressoExecuter(executers.BaseExecuter):
    """Executer class for the QuantumEspresso simulator."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        if self.args.use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

        commands = self.args.commands

        for command in commands:
            is_openmp = "_openmp" in command
            # Some commands from the mpi build do not support mpi
            mpi_disabled = command in QuantumEspressoCommand.MPI_DISABLED

            if not is_openmp and not mpi_disabled:
                cmd = QuantumEspressoCommand(command["cmd"],
                                             command["prompts"],
                                             is_mpi=True)
            else:
                cmd = QuantumEspressoCommand(command["cmd"],
                                             command["prompts"],
                                             is_mpi=False)
            self.run_subprocess(cmd, self.artifacts_dir)
