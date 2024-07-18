"""Dataclass for MPI configuration."""
import shlex
from typing import List, Optional


class MPIConfiguration():
    """Dataclass for MPI configuration."""
    hostfile_path: Optional[str]
    share_path: Optional[str]
    extra_args: List[str]
    mpirun_bin_path: str

    def __init__(
        self,
        hostfile_path: Optional[str] = None,
        share_path: Optional[str] = None,
        extra_args: str = "",
        mpi_run_bin_path: str = "mpirun",
    ):
        self.hostfile_path = hostfile_path
        self.share_path = share_path
        self.extra_args = shlex.split(extra_args)
        self.mpirun_bin_path = mpi_run_bin_path
