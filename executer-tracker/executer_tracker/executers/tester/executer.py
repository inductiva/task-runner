"""Dummy executer for testing purposes."""
import os
import shutil
import time

import json


from executer_tracker import executers



class TestExecuter(executers.BaseExecuter):

    def execute(self):
        input_file = self.args.input_filename
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        commands = self.args.commands
        sleep_time = self.args.sleep_time

        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)
        os.chdir(self.artifacts_dir)
       
        filenames_list = os.listdir(input_dir)
        with open("test_arguments.json", "w", encoding="utf-8") as f:
            args = {"input_filename": input_file,
                    "input_dir_list": filenames_list,
                    "commands": commands, "sleep_time": sleep_time}
            json.dump(args, f)
            
        time.sleep(sleep_time)

        if commands is not None:
            for command in commands:
                command = executers.Command(command["cmd"], command["prompts"])
                self.run_subprocess(command, working_dir=self.artifacts_dir)
