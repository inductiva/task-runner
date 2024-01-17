import os
import shutil

import time

from executer_tracker import executers



class TestExecuter(executers.BaseExecuter):

    def execute(self):
        input_file = self.args.input_filename
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        commands = self.args.commands
        sleep_time = self.args.sleep_time

        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)
        os.chdir(self.artifacts_dir)
        
        with open("test_arguments.txt", "w", encoding="utf-8") as f:
            f.write(f"Input file: {input_file}")
            f.write(f"Input directory: {self.args.sim_dir}")
            f.write(f"Commands: {commands}")
            f.write(f"Sleep time: {sleep_time}")

        time.sleep(sleep_time)

        for command in commands:
            command = executers.Command(command["cmd"], command["prompts"])
            self.run_subprocess(command, working_dir=self.artifacts_dir)
