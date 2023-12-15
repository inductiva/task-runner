"""Dataclass for MPI configuration."""
from typing import List
import shlex


class MPIConfiguration():
    hostfile_path: str
    share_path: str
    extra_args: List[str]

    def __init__(self, hostfile_path: str, share_path: str, extra_args: str):
        self.hostfile_path = hostfile_path
        self.share_path = share_path
        self.extra_args = shlex.split(extra_args)
