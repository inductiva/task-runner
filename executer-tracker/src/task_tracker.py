# pylint: disable=missing-module-docstring
from docker.types import Mount

from absl import logging


class TaskTracker:
    # pylint: disable=missing-class-docstring
    def __init__(self, docker, image, command, working_dir_host):
        self.docker = docker
        self.image = image
        self.command = command
        self.working_dir_host = working_dir_host
        self.container = None

    def run(self):
        logging.info("Working dir: %s", self.working_dir_host)
        self.container = self.docker.containers.run(
            self.image,
            self.command,
            mounts=[
                Mount(
                    "/working_dir",
                    self.working_dir_host,
                    type="bind",
                ),
            ],
            working_dir="/working_dir",
            detach=True,
        )

    def wait(self) -> int:
        status = self.container.wait()
        return status["StatusCode"]

    def kill(self):
        self.container.kill()

    def cleanup(self):
        self.container.remove()
