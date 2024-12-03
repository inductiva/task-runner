"""Task-Runner for FVCOM"""
import os
import shutil

from task_runner import executers


class FVCOMCommand(executers.Command):
    """FVCOM command."""

    def _check_security(self, tokens, prompts):
        super()._check_security(tokens, prompts)
        if not self.args[0].startswith("fvcom"):
            raise ValueError("The command must start with 'fvcom'.")


class FVCOMExecuter(executers.BaseExecuter):
    """Executer class for the FVCOM simulator."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        #debug level used, always present (from 0 to 7)
        debug = self.args.debug
        #used to pick the binary to run (empty string for default fvcom)
        model = self.args.model
        #case name used in the simulation (empty string means no --CASENAME)
        case_name = self.args.case_name
        #place where the fvcom executable will be executed
        working_dir = self.args.working_dir
        #create_namelist flag (empty string means no --CREATE_NAMELIST)
        create_namelist = self.args.create_namelist

        if case_name:
            case_name = f"--CASENAME={case_name}"

        if create_namelist:
            create_namelist = f"--CREATE_NAMELIST {create_namelist}"

        if model:
            model = f"_{model.lower()}"

        cmd = f"fvcom{model} {case_name} {create_namelist} --dbg={debug}"

        if self.args.n_vcpus:
            self.mpi_config.extra_args.extend(["-np", f"{self.args.n_vcpus}"])

        if self.args.use_hwthread:
            self.mpi_config.extra_args.extend(["--use-hwthread-cpus"])

        fvcom_cmd = FVCOMCommand(cmd, is_mpi=True)

        self.run_subprocess(fvcom_cmd,
                            os.path.join(self.artifacts_dir, working_dir))
