"""Class for MPI configuration."""
import glob
import os
import re
import shlex
from typing import Optional

from task_runner.executers import command

DEFAULT_VERSION = "4.1.6"


class MPIClusterConfiguration():
    """Class for MPI configuration."""
    hostfile_path: Optional[str]
    share_path: Optional[str]
    extra_args: list[str]
    mpirun_bin_path_template: str
    local_mode: bool

    def __init__(
        self,
        default_version: str = DEFAULT_VERSION,
        is_cluster: bool = False,
        hostfile_path: Optional[str] = None,
        share_path: Optional[str] = None,
        extra_args: str = "",
        mpirun_bin_path_template: str = "mpirun",
        num_hosts: int = 1,
        local_mode: bool = True,
    ):
        self.is_cluster = is_cluster
        self.hostfile_path = hostfile_path
        self.share_path = share_path
        self.extra_args = shlex.split(extra_args)
        self.mpirun_bin_path_template = mpirun_bin_path_template
        self.num_hosts = num_hosts
        self.default_version = default_version
        self.mpi_version_regexp = re.compile(
            self.mpirun_bin_path_template.format(version="(.*)"))
        self.local_mode = local_mode

    @classmethod
    def from_env(cls):
        is_cluster_str = os.getenv("MPI_CLUSTER", "false")
        is_cluster = is_cluster_str.lower() in ("true", "t", "yes", "y", 1)

        mpi_share_path = None
        mpi_hostfile_path = None
        mpi_extra_args = os.getenv("MPI_EXTRA_ARGS", "--allow-run-as-root")
        mpirun_bin_path_template = os.getenv("MPIRUN_BIN_PATH_TEMPLATE",
                                             "mpirun")
        mpi_default_version = os.getenv("MPI_DEFAULT_VERSION", DEFAULT_VERSION)

        local_mode = os.getenv("LOCAL_MODE",
                               "true").lower() in ("true", "t", "yes", "y", 1)

        num_hosts = 1
        if is_cluster:
            mpi_share_path = os.getenv("MPI_SHARE_PATH", None)
            mpi_hostfile_path = os.getenv("MPI_HOSTFILE_PATH", None)
            if not mpi_share_path:
                raise RuntimeError(
                    "MPI_SHARE_PATH environment variable not set.")

            if not mpi_hostfile_path:
                raise RuntimeError(
                    "MPI_HOSTFILE_PATH environment variable not set.")

            with open(mpi_hostfile_path, "r", encoding="UTF-8") as f:
                hosts = [line for line in f.readlines() if line.strip() != ""]
                num_hosts = len(hosts)

        return cls(
            is_cluster=is_cluster,
            hostfile_path=mpi_hostfile_path,
            share_path=mpi_share_path,
            extra_args=mpi_extra_args,
            mpirun_bin_path_template=mpirun_bin_path_template,
            num_hosts=num_hosts,
            default_version=mpi_default_version,
            local_mode=local_mode,
        )

    def list_available_versions(self) -> list[str]:
        mpirun_bin_paths = glob.glob(
            self.mpirun_bin_path_template.format(version="*"))

        versions = []
        for path in mpirun_bin_paths:
            match = self.mpi_version_regexp.match(path)
            if match is not None:
                versions.append(match.group(1))

        versions.sort()

        return versions

    def get_mpirun_bin_path(self, version: str) -> str:
        mpirun_bin_path = self.mpirun_bin_path_template.format(version=version)
        if not os.path.exists(mpirun_bin_path):
            available_versions = self.list_available_versions()
            raise RuntimeError(
                f"The request MPI version ({version}) is not available. "
                f"Available versions: {', '.join(available_versions)}")
        return mpirun_bin_path

    def build_command_prefix(
        self,
        command_config: Optional[command.MPICommandConfig] = None,
    ) -> list[str]:
        version = self.default_version

        user_provided_args = []
        if command_config is not None:
            version = command_config.version
            user_provided_args = command_config.args

        mpirun_bin_path = self.get_mpirun_bin_path(version)

        args = [mpirun_bin_path]

        if self.hostfile_path is not None:
            args.extend([
                "--hostfile",
                self.hostfile_path,
            ])
        args.extend(self.extra_args)
        args.extend(user_provided_args)

        return args
