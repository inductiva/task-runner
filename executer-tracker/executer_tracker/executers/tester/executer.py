import os
import shutil
import psutil

from executer_tracker import executers

class TestExecuter(executers.BaseExecuter):

    def execute(self):
        n_cores = psutil.cpu_count(logical=False)
        input_file = self.args.input_filename
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        commands = self.args.commands

        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)

        for command in commands:
            command = executers.Command(command["cmd"], command["prompts"])
            self.run_subprocess(command, working_dir=self.artifacts_dir)
