"""Executer to run arbitrary commands."""

import os
import shutil

from task_runner import executers


class ArbitraryCommandsExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run arbitrary commands."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        working_dir = self.args.working_dir or self.artifacts_dir

        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        for command in self.args.commands:
            cmd = executers.Command.from_dict(command)
            self.run_subprocess(cmd, working_dir=working_dir)
