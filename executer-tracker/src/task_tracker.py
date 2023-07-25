"""Class for running and tracking a task in a Docker container."""
from typing import Optional
import docker
from docker.types import Mount
from docker.models.containers import Container

from absl import logging


class TaskTracker:
    """Run and track a task in a Docker container.

    Attributes:
        docker: Docker client.
        image: Docker image to run.
        command: Command to run in the container.
        working_dir_host: Path to the working directory in the host of the
            container. This directory is bind-mounted to the container.
        container: The container running the task. Property is None until
            the run method is called.
    """

    def __init__(self, docker_client: docker.DockerClient, image: str,
                 command: str, working_dir_host: str):
        """Initialize the task tracker.

        Args described in class docstring.
        """
        self.docker = docker_client
        self.image = image
        self.command = command
        self.working_dir_host = working_dir_host
        self.container: Optional[Container] = None

    def run(self):
        """Runs the task in a Docker container in detached mode."""
        container_working_dir = "/working_dir"

        container = self.docker.containers.run(
            self.image,
            self.command,
            mounts=[
                Mount(
                    container_working_dir,
                    self.working_dir_host,
                    type="bind",
                ),
            ],
            working_dir=container_working_dir,
            detach=True,  # Run container in background.
            auto_remove=True,  # Remove container when it exits.
        )
        assert isinstance(
            container,
            Container), "Launched container is not of type Container."

        self.container = container

    def wait(self) -> int:
        """Blocks until end of execution, returning the command's exit code."""
        if not self.container:
            raise RuntimeError("Container not running.")

        for s in self.container.stats(decode=True):
            # Reference:
            # - https://docs.docker.com/engine/reference/commandline/stats/#description # disable=line-too-long
            # - https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerStats # disable=line-too-long
            logging.info("Read: %s", s["read"])
            used_memory = s["memory_stats"]["usage"] - s["memory_stats"][
                "stats"]["inactive_file"]
            available_memory = s["memory_stats"]["limit"]
            memory_usage_percent = used_memory / available_memory * 100
            logging.info("Memory usage: %s", memory_usage_percent)
            cpu_delta = s["cpu_stats"]["cpu_usage"]["total_usage"] - s[
                "precpu_stats"]["cpu_usage"]["total_usage"]

            try:
                precpu_system_cpu_usage = s["precpu_stats"]["system_cpu_usage"]
            except KeyError:
                # This happens on the first read.
                precpu_system_cpu_usage = 0

            system_cpu_delta = (s["cpu_stats"]["system_cpu_usage"] -
                                precpu_system_cpu_usage)
            number_cpus = s["cpu_stats"]["online_cpus"]
            cpu_usage_percent = (cpu_delta /
                                 system_cpu_delta) * number_cpus * 100
            logging.info("CPU usage: %s", cpu_usage_percent)

        status = self.container.wait()

        return status["StatusCode"]

    def kill(self):
        """Kills the running container."""
        if not self.container:
            raise RuntimeError("Container not running.")

        self.container.kill()
