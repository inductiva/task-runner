"""Executer to run arbitrary commands."""

import os
import shutil

from task_runner import executers
from task_runner.utils import files


class ArbitraryCommandsExecuter(executers.BaseExecuter):
    """Concrete implementation of an Executer to run arbitrary commands."""

    def execute(self):
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)

        run_subprocess_dir = self.artifacts_dir_container

        if hasattr(self.args,
                   'run_subprocess_dir') and self.args.run_subprocess_dir:
            run_subprocess_dir = os.path.join(self.artifacts_dir_container,
                                              self.args.run_subprocess_dir)

        # Copy the input files to the artifacts directory
        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        # Save this timestamp to detect which files were created or modified
        timestamp = files.get_most_recent_timestamp(self.artifacts_dir)

        try:
            for command in self.args.commands:
                cmd = executers.Command.from_dict(command)
                self.run_subprocess(cmd, working_dir=run_subprocess_dir)
        finally:
            # Remove files that were not modified or created
            if not timestamp:
                return
            files.remove_before_time(directory=self.artifacts_dir,
                                     reference_time_ns=timestamp)
