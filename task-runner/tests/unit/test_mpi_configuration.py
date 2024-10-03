from unittest import mock

import pytest
from task_runner.executers import command, mpi_configuration

MPIRUN_BIN_PATH_TEMPLATE = "/opt/openmpi/{version}/bin/mpirun"


@pytest.fixture(name="mpi_config")
def fixture_mpi_config():
    mpi_config = mpi_configuration.MPIClusterConfiguration(
        default_version="1.2.3",
        is_cluster=True,
        hostfile_path=None,
        share_path=None,
        extra_args="",
        mpirun_bin_path_template="mpirun",
        num_hosts=2,
    )
    mpi_config.get_mpirun_bin_path = mock.Mock(
        side_effect=lambda v: MPIRUN_BIN_PATH_TEMPLATE.format(version=v))
    return mpi_config


def test_build_command_prefix(mpi_config):
    version = "1.2.3"
    args = mpi_config.build_command_prefix(
        command_config=command.MPICommandConfig.from_dict({
            "version": version,
            "options": {
                "np": 4,
                "use-hwthread-cpus": True,
            },
        }))

    assert args == [
        MPIRUN_BIN_PATH_TEMPLATE.format(version=version), "--np", "4",
        "--use-hwthread-cpus"
    ]

    args = mpi_config.build_command_prefix(
        command_config=command.MPICommandConfig.from_dict({
            "version": version,
            "options": {
                "np": 4,
                "use-hwthread-cpus": False,
            },
        }))
    assert args == [
        MPIRUN_BIN_PATH_TEMPLATE.format(version=version),
        "--np",
        "4",
    ]

    args = mpi_config.build_command_prefix(
        command_config=command.MPICommandConfig.from_dict({
            "version": version,
            "options": {
                "np": 4,
            },
        }))
    assert args == [
        MPIRUN_BIN_PATH_TEMPLATE.format(version=version),
        "--np",
        "4",
    ]
