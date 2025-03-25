"""Utils related to Apptainer images.

Includes the ApptainerImagesManager class, which is used to fetch Apptainer
images from a remote storage and cache them locally.
"""
import enum
import os
import re
import subprocess
import time
from typing import Optional

import fsspec
import requests
from absl import logging

import task_runner

INDUCTIVA_IMAGE_PREFIX = "inductiva://"


class ApptainerImageSource(enum.Enum):
    LOCAL_FILESYSTEM = "local-filesystem"
    INDUCTIVA_APPTAINER_CACHE = "inductiva-apptainer-cache"
    DOCKER_HUB = "docker-hub"
    USER_STORAGE = "user-storage"


class ApptainerImageNotFoundError(Exception):
    pass


class ApptainerImagesManager:
    """Downloads and caches Apptainer .sif images.

    Attributes:
        local_cache_dir: Path to the local directory where the Apptainer
            images will be cached.
        remote_storage_filesystem: fsspec filesystem object used to retrieve
            the Apptainer images from the remote storage.
        remote_storage_dir: Path to the directory in the remote storage where
            the Apptainer images are stored.
    """

    def __init__(
        self,
        local_cache_dir: str,
        file_manager: task_runner.BaseFileManager,
        remote_storage_url: Optional[str] = None,
    ):
        self._local_cache_dir = local_cache_dir
        os.makedirs(self._local_cache_dir, exist_ok=True)

        self._remote_storage_filesystem = None
        self._remote_storage_dir = None

        if remote_storage_url is not None:
            remote_storage_spec, remote_storage_dir = (
                remote_storage_url.split("://"))
            self._remote_storage_filesystem = fsspec.filesystem(
                remote_storage_spec)
            self._remote_storage_dir = remote_storage_dir

        self._file_manager = file_manager

    def _normalize_image_uri(self, image_uri: str) -> str:
        """Check if the image URI is fully qualified.

        If not, include the default URI prefix 'docker://'.
        """
        if "://" in image_uri:
            uri_prefix, image_name = image_uri.split("://")
        else:
            uri_prefix = "docker"
            image_name = image_uri

        return f"{uri_prefix}://{image_name}"

    def _image_uri_to_sif_name(self, image_uri: str) -> str:
        """Converts a image URI to a SIF image name.

        Note that the conversion must follow the same conversion used in the
        Cloud Build trigger that converts Docker images to Apptainer images.
        Cloud Build definition is in .gcloud/build_apptainer_images.yaml.

        Example:
            "docker://inductiva/kutu:openfoam-foundation_v8_dev" ->
                "docker_inductiva_kutu_openfoam-foundation_v8_dev.sif"
        """
        return re.sub(r"://|:|/", "_", image_uri) + ".sif"

    def _apptainer_pull(self, image_uri: str, sif_local_path: str):
        """Pulls the image from Docker Hub and converts it to a SIF image.

        Raises:
            ApptainerImageNotFoundError: If pulling the image fails.
        """
        logging.info("Pulling image ...")

        try:
            subprocess_env = os.environ.copy(
            )  # Copy the current environment to preserve it

            socks_proxy_host = os.getenv('SOCKS_PROXY_HOST', None)
            socks_proxy_port = os.getenv('SOCKS_PROXY_PORT', None)
            if socks_proxy_host and socks_proxy_port:
                subprocess_env[
                    'HTTP_PROXY'] = f"socks5://{socks_proxy_host}:{socks_proxy_port}"
                subprocess_env[
                    'HTTPS_PROXY'] = f"socks5://{socks_proxy_host}:{socks_proxy_port}"
            subprocess.run(
                [
                    "apptainer",
                    "pull",
                    sif_local_path,
                    image_uri,
                ],
                check=True,
                env=subprocess_env,  # subprocess should inherit the environment
                # because of APPTAINER environment variables
            )
        except subprocess.CalledProcessError:
            raise ApptainerImageNotFoundError(
                f"Failed to pull image: {image_uri}")
        except FileNotFoundError:
            raise ApptainerImageNotFoundError(
                "Apptainer command not available.")

    def _get_from_remote_storage(
        self,
        sif_image_name: str,
        sif_local_path: str,
    ) -> bool:
        """Attempt to download the image from the remote storage.

        If a remote storage was not provided on object creation, this method
        won't do anything.

        Returns:
            True if the image was found in the remote storage and downloaded,
            False otherwise.
        """
        if (self._remote_storage_dir
                is None) or (self._remote_storage_filesystem is None):
            return False

        sif_remote_path = os.path.join(self._remote_storage_dir, sif_image_name)

        if self._remote_storage_filesystem.exists(sif_remote_path):
            logging.info("SIF image found in remote storage: %s",
                         sif_image_name)
            logging.info("Downloading from remote remote storage...")
            self._remote_storage_filesystem.download(
                sif_remote_path,
                sif_local_path,
            )
            logging.info("Downloaded SIF image to: %s", sif_local_path)
            return True

        logging.info("SIF image not found in remote storage: %s",
                     sif_image_name)

        return False

    def _download_inductiva_image(
        self,
        image_path: str,
        sif_local_path: str,
    ) -> bool:
        """Downloads a .sif image from a GSB using a signed URL.

        Args:
            image_path: The file path within the bucket.
            sif_local_path: Local path where the image will be stored.

        Returns:
            True if the image was successfully downloaded; False otherwise.
        """
        try:
            self._file_manager.download_input_resources(
                [image_path],
                sif_local_path,
            )
            return True
        except Exception:
            return False

    def _parse_inductiva_uri(self, image: str) -> tuple[str, str]:
        """Extracts the bucket and file path from an Inductiva URI."""
        try:
            return image.removeprefix(INDUCTIVA_IMAGE_PREFIX)
        except ValueError:
            raise ApptainerImageNotFoundError(
                f"Invalid Inductiva image format: {image}")

    def _get_local_sif_path(self, image_path) -> str:
        """Generates a local cache file path for an Inductiva image."""
        return os.path.join(self._local_cache_dir,
                            f"inductiva_{os.path.basename(image_path)}")

    def _pull_or_fetch_remote_image(self, image_uri: str,
                                    sif_local_path: str) -> bool:
        """Fetches an image from remote storage or pulls it using Apptainer."""
        if self._get_from_remote_storage(self._image_uri_to_sif_name(image_uri),
                                         sif_local_path):
            return True
        logging.info("Pulling image")
        self._apptainer_pull(image_uri, sif_local_path)
        return os.path.exists(sif_local_path)

    def get(self, image: str) -> tuple[str, float, ApptainerImageSource]:
        """Fetches the requested Apptainer image and makes it available locally.

        If the image is an Inductiva image, it is downloaded via a signed URL.
        Otherwise, it is fetched from the remote storage or pulled 
        using Apptainer.

        Args:
            image: The image URI or file name.

        Returns:
            A tuple containing:
                - The local path to the Apptainer image.
                - The time taken to fetch the image.
                - The image source.

        Raises:
            ApptainerImageNotFoundError: If the image cannot be retrieved.
        """
        logging.info("Fetching SIF image: %s", image)

        # Determine if the image is Inductiva-based
        if image.startswith(INDUCTIVA_IMAGE_PREFIX):
            image_path = self._parse_inductiva_uri(image)
            sif_local_path = self._get_local_sif_path(image_path)
            image_source = ApptainerImageSource.INDUCTIVA_HUB
            fetch_method = self._download_inductiva_image
            fetch_args = (image_path, sif_local_path)
        else:
            image_uri = self._normalize_image_uri(image)
            sif_local_path = os.path.join(
                self._local_cache_dir, self._image_uri_to_sif_name(image_uri))
            image_source = ApptainerImageSource.DOCKER_HUB
            fetch_method = self._pull_or_fetch_remote_image
            fetch_args = (image_uri, sif_local_path)

        # Return if already cached
        logging.info(f"sif_local_path: {sif_local_path}")
        if os.path.exists(sif_local_path):
            logging.info("SIF image found locally: %s", sif_local_path)
            return (sif_local_path, 0, ApptainerImageSource.LOCAL_FILESYSTEM,
                    os.path.getsize(sif_local_path))

        # Attempt to fetch the image
        download_start = time.time()
        if not fetch_method(*fetch_args):
            raise ApptainerImageNotFoundError(f"Image not found: {image}")
        download_time = time.time() - download_start

        return sif_local_path, download_time, image_source, os.path.getsize(
            sif_local_path)
