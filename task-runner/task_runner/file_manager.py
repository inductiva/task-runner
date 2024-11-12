import abc
import os
import time
import urllib
import urllib.request
import uuid
from typing import List

import requests
from typing_extensions import override

import task_runner
from task_runner import utils
from task_runner.utils import files


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

    @abc.abstractmethod
    def download_input_resources(
        self,
        input_resources: List[str],
        dest_path: str,
        task_runner_id: uuid.UUID,
    ):
        pass


class WebApiFileManager(BaseFileManager):
    REQUEST_TIMEOUT_S = 60

    def __init__(
        self,
        api_client: task_runner.ApiClient,
        task_runner_id: uuid.UUID,
    ):
        self._api_client = api_client
        self._task_runner_id = task_runner_id

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
            self._task_runner_id,
            task_id,
        )
        urllib.request.urlretrieve(url, dest_path)

    @utils.execution_time_with_result
    @override
    def upload_output(
        self,
        task_id: str,
        task_dir_remote: str,
        local_path: str,
        stream_zip: bool = True,
    ):
        del task_dir_remote  # unused

        if stream_zip:
            data = files.get_zip_generator(local_path)
            zip_duration = 0
        else:
            zip_path, zip_duration = files.make_zip_archive(local_path)
            data = open(zip_path, "rb")

        upload_info = self._api_client.get_upload_output_url(
            task_runner_id=self._task_runner_id, task_id=task_id)

        start_time = time.time()
        resp = requests.request(
            method=upload_info.method,
            url=upload_info.url,
            data=data,
            timeout=self.REQUEST_TIMEOUT_S,
            headers={
                "Content-Type": "application/octet-stream",
            },
        )
        upload_time = time.time() - start_time

        resp.raise_for_status()

        if stream_zip:
            size = data.total_bytes
        else:
            data.close()
            size = os.path.getsize(zip_path)
            os.remove(zip_path)

        return size, zip_duration, upload_time

    @utils.execution_time
    @override
    def download_input_resources(
        self,
        input_resources: List[str],
        dest_path: str,
        task_runner_id: uuid.UUID,
    ):
        files_url = self._api_client.get_download_urls(input_resources,
                                                       task_runner_id)

        for file_url in files_url:
            url = file_url["url"]
            base_path = file_url["file_path"]
            file_path = os.path.join(dest_path, base_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            urllib.request.urlretrieve(url, file_path)
