"""Class for running and tracking a task in a Docker container."""
import os
from typing import Optional

import docker
import docker.types
from absl import logging
from docker.models.containers import Container
from utils import config


class TaskTracker:
    """Run and track a task in a Docker container.

    Attributes:
        docker: Docker client.
        executer_config: Docker image to run.
        command: Command to run in the container.
        working_dir_host: Path to the working directory in the host of the
            container. This directory is bind-mounted to the container.
        container: The container running the task. Property is None until
            the run method is called.
    """

    def __init__(self, docker_client: docker.DockerClient,
                 executer_config: config.ExecuterConfig, command: str,
                 working_dir_host: str):
        """Initialize the task tracker.

        Args described in class docstring.
        """
        self.docker = docker_client
        self.executer_config = executer_config
        self.command = command
        self.working_dir_host = working_dir_host
        self.container: Optional[Container] = None

    def run(self):
        """Runs the task in a Docker container in detached mode."""
        container_working_dir = "/working_dir"

        device_requests = []
        if self.executer_config.use_gpu:
            gpu_request = docker.types.DeviceRequest(
                driver="nvidia",
                capabilities=[["gpu"]],
                count=-1,  # allow access to all GPUs
            )
            device_requests.append(gpu_request)

        container = self.docker.containers.run(
            self.executer_config.image,
            self.command,
            mounts=[
                docker.types.Mount(
                    container_working_dir,
                    self.working_dir_host,
                    type="bind",
                ),
            ],
            working_dir=container_working_dir,
            detach=True,  # Run container in background.
            auto_remove=False,
            device_requests=device_requests)
        assert isinstance(
            container,
            Container), "Launched container is not of type Container."

        self.container = container

    def wait(self,
             stdout_file=None,
             stdout_file_remote=None,
             artifact_filesystem=None,
             resource_file_remote=None) -> int:
        """Blocks until end of execution, returning the command's exit code."""
        if not self.container:
            raise RuntimeError("Container not running.")

        for s in self.container.stats(decode=True):
            # Reference:
            # - https://docs.docker.com/engine/reference/commandline/stats/#description # noqa: E501
            # - https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerStats # noqa: E501
            self.container.reload()
            if self.container.status in ("exited", "dead"):
                break

            try:
                timestamp = s["read"]
                logging.info("Read: %s", timestamp)
                used_memory = s["memory_stats"]["usage"] - s["memory_stats"][
                    "stats"]["inactive_file"]
                available_memory = s["memory_stats"]["limit"]
                memory_usage_percent = used_memory / available_memory * 100
                logging.info("Memory usage: %s", memory_usage_percent)
                cpu_delta = s["cpu_stats"]["cpu_usage"]["total_usage"] - s[
                    "precpu_stats"]["cpu_usage"]["total_usage"]
            except KeyError as e:
                logging.error("KeyError: %s", str(e))
                logging.info("Stats dict: %s", str(s))
                continue

            try:
                precpu_system_cpu_usage = s["precpu_stats"]["system_cpu_usage"]
            except KeyError:
                # This happens on the first read.
                precpu_system_cpu_usage = 0

            try:
                system_cpu_delta = (s["cpu_stats"]["system_cpu_usage"] -
                                    precpu_system_cpu_usage)
                number_cpus = s["cpu_stats"]["online_cpus"]
                cpu_usage_percent = (cpu_delta /
                                     system_cpu_delta) * number_cpus * 100
                logging.info("CPU usage: %s", cpu_usage_percent)
            except KeyError:
                continue

            if stdout_file is not None and stdout_file_remote is not None:
                if os.path.exists(stdout_file):
                    with artifact_filesystem.open_output_stream(
                            path=stdout_file_remote) as std_file:
                        with open(stdout_file, "rb") as f_src:
                            std_file.write(f_src.read())

            if resource_file_remote is not None:
                with artifact_filesystem.open_output_stream(
                        path=resource_file_remote) as r_file:
                    current_usage = f"{timestamp}, {memory_usage_percent}, {cpu_usage_percent} \n"  # noqa: E501
                    r_file.write(current_usage.encode("utf-8"))

        status = self.container.wait()
        self.container.remove()
        return status["StatusCode"]

    def kill(self):
        """Kills the running container."""
        if not self.container:
            raise RuntimeError("Container not running.")

        self.container.kill()
