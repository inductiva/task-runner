"""Executer to run arbitrary commands."""

import getpass
import os
import shutil

from task_runner import executers
from task_runner.utils import files
from absl import logging


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

        original_username = None
        if self.commands_user:
            original_username = getpass.getuser()
            os.system(f"sudo chown -R {self.commands_user} {self.working_dir}")

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

            files_to_remove = files.remove_before_time(
                directory=self.artifacts_dir, reference_time_ns=timestamp)

            if original_username:
                os.system(
                    f"sudo chown -R {original_username} {self.working_dir}")

            for f in files_to_remove:
                f.unlink(missing_ok=True)
