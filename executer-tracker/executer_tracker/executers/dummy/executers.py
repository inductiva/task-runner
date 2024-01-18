"""Dummy executers for testing purposes."""
from executer_tracker import executers


class MPIHelloWorldExecuter(executers.BaseExecuter):
    """Run a sample MPI hello world program."""

    def execute(self):
        cmd = executers.Command("/opt/mpi_hello_world", is_mpi=True)
        self.run_subprocess(cmd)
