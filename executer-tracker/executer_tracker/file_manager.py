import abc
import os
import shutil
import urllib
import urllib.request
import uuid

import fsspec
import requests
from typing_extensions import override

import executer_tracker
from executer_tracker import utils


class BaseFileManager(abc.ABC):

    @abc.abstractmethod
    def download_input(
        self,
        task_id: str,
        task_dir_remote: str,
        dest_path: str,
    ):
        pass

    @abc.abstractmethod
    def upload_output(
        self,
        task_id: str,
        task_dir_remote: str,
        local_path: str,
    ):
        pass


class FsspecFileManager(BaseFileManager):

    def __init__(self, artifact_store_root: str):
        protocol = "gs" if artifact_store_root == "gs://" else "file"
        self._filesystem = fsspec.filesystem(protocol)
        self._artifact_store_root = artifact_store_root

    @utils.execution_time
    @override
    def download_input(
        self,
        task_id: str,
        task_dir_remote: str,
        dest_path: str,
    ):
        del task_id  # unused

        remote_path = os.path.join(
            self._artifact_store_root,
            task_dir_remote,
            utils.INPUT_ZIP_FILENAME,
        )

        with self._filesystem.open(remote_path, "rb") as f:
            with open(dest_path, "wb") as local_file:
                shutil.copyfileobj(f, local_file)

    @utils.execution_time
    @override
    def upload_output(
        self,
        task_id: str,
        task_dir_remote: str,
        local_path: str,
    ):
        del task_id  # unused

        remote_path = os.path.join(
            self._artifact_store_root,
            task_dir_remote,
            utils.OUTPUT_ZIP_FILENAME,
        )
        with open(local_path, "rb") as f_src:
            with self._filesystem.open(remote_path, "wb") as f_dest:
                shutil.copyfileobj(f_src, f_dest)


class WebApiFileManager(BaseFileManager):
    REQUEST_TIMEOUT_S = 60

    def __init__(
        self,
        api_client: executer_tracker.ApiClient,
        executer_tracker_id: uuid.UUID,
    ):
        self._api_client = api_client
        self._executer_tracker_id = executer_tracker_id

    @utils.execution_time
    @override
    def download_input(
        self,
        task_id: str,
        task_dir_remote: str,
        dest_path: str,
    ):
        del task_dir_remote  # unused

        url = self._api_client.get_download_input_url(
            self._executer_tracker_id,
            task_id,
        )
        urllib.request.urlretrieve(url, dest_path)

    @utils.execution_time
    @override
    def upload_output(
        self,
        task_id: str,
        task_dir_remote: str,
        local_path: str,
    ):
        del task_dir_remote  # unused

        upload_info = self._api_client.get_upload_output_url(
            executer_tracker_id=self._executer_tracker_id, task_id=task_id)

        with open(local_path, "rb") as f:
            resp = requests.request(
                method=upload_info.method,
                url=upload_info.url,
                data=f,
                timeout=self.REQUEST_TIMEOUT_S,
                headers={
                    "Content-Type": "application/octet-stream",
                },
            )

        resp.raise_for_status()
