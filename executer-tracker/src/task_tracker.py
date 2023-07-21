"""Class for running and tracking a task in a Docker container."""
from typing import Optional
import docker
from docker.types import Mount
from docker.models.containers import Container


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

        self.container.logs()
        status = self.container.wait()

        return status["StatusCode"]

    def kill(self):
        """Kills the running container."""
        if not self.container:
            raise RuntimeError("Container not running.")

        self.container.kill()
