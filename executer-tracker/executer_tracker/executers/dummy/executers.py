"""Dummy executers for testing purposes."""
import os
import shutil
import time

from executer_tracker import executers


class MPIHelloWorldExecuter(executers.BaseExecuter):
    """Run a sample MPI hello world program."""

    def execute(self):
        cmd = executers.Command("/opt/mpi_hello_world", is_mpi=True)
        self.run_subprocess(cmd)


class DummyExecuter(executers.BaseExecuter):
    """Dummy executer for testing purposes."""

    def execute(self):
        input_file = self.args.input_filename
        input_dir = os.path.join(self.working_dir, self.args.sim_dir)
        sleep_time = self.args.sleep_time

        shutil.copytree(input_dir, self.artifacts_dir, dirs_exist_ok=True)
        os.chdir(self.artifacts_dir)
        filenames_list = os.listdir(input_dir)
        args = {
            "input_filename": input_file,
            "input_dir_list": filenames_list,
            "sleep_time": sleep_time
        }

        output_file_path = os.path.abspath(
            os.path.join(self.artifacts_dir, "test_arguments.json"))

        time.sleep(sleep_time)
        self.run_subprocess(
            executers.Command(f"/dummy.sh \"${args}\" {output_file_path}"))
