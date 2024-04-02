"""Generic Openfast executer."""
import os
import shutil

from executer_tracker import executers


class OpenfastCommand(executers.Command):
    """Openfast command."""
    ALLOWED_COMMANDS = [
        "aerodyn_driver", "beamdyn_driver", "feam_driver", "hydrodyn_driver",
        "inflowwind_driver", "moordyn_driver", "openfast", "orca_driver",
        "servodyn_driver", "subdyn_driver", "turbsim", "unsteadyaero_driver"
    ]

    def _check_security(self, tokens, prompts):
        super()._check_security(tokens, prompts)
        if self.args[0] not in OpenfastCommand.ALLOWED_COMMANDS:
            raise ValueError("Command not allowed. Valid commands are: "
                             f"{OpenfastCommand.ALLOWED_COMMANDS}")


class OpenfastExecuter(executers.BaseExecuter):
    """Openfast executer."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        commands = self.args.commands

        for command in commands:
            command = OpenfastCommand(command["cmd"], command["prompts"])

            self.run_subprocess(command, self.artifacts_dir)
