import abc
import os
import pathlib
import urllib
import urllib.request
import uuid

import requests
import requests.adapters
import urllib3
from typing_extensions import override

import task_runner
from task_runner import utils
from task_runner.operations_logger import OperationName, OperationsLogger
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
        operations_logger: OperationsLogger,
        stream_zip: bool = True,
        compress_with: str = "AUTO",
    ):
        pass

    @abc.abstractmethod
    def download_input_resources(
        self,
        input_resources: list[str],
        dest_path: str,
        task_runner_id: uuid.UUID,
        workdir: str,
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

    def _get_storage_dir(self, task_dir_remote: str) -> str:
        """Removes the user bucket prefix from `task_dir_remote`"""
        task_path = pathlib.Path(task_dir_remote)
        storage_dir = task_path.relative_to(task_path.parts[0])
        return str(storage_dir)

    @utils.execution_time
    @override
    def download_input(
        self,
        task_id: str,
        task_dir_remote: str,
        dest_path: str,
    ):
        storage_dir = self._get_storage_dir(task_dir_remote)
        url = self._api_client.get_download_input_url(storage_dir)
        urllib.request.urlretrieve(url, dest_path)

    @staticmethod
    @utils.execution_time_with_result
    def upload(method: str, url: str, data) -> requests.Response:
        retry = urllib3.Retry(
            total=None,  # no limit on retry count
            backoff_factor=2,  # exponential backoff factor
            status_forcelist=[
                403,  # Forbidden
                408,  # Request Timeout
                429,  # Too Many Requests
                500,  # Internal Server Error
                502,  # Bad Gateway
                503,  # Service Unavailable
                504,  # Gateway Timeout
            ],  # the HTTP status codes to retry on
        )

        adapter = requests.adapters.HTTPAdapter(max_retries=retry)

        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session.request(
            method=method,
            url=url,
            data=data,
            timeout=WebApiFileManager.REQUEST_TIMEOUT_S,
            headers={"Content-Type": "application/octet-stream"},
        )

    @override
    def upload_output(
        self,
        task_id: str,
        task_dir_remote: str,
        local_path: str,
        operations_logger: OperationsLogger,
        stream_zip: bool = True,
        compress_with: str = "AUTO",
    ):
        if stream_zip:
            if compress_with == "SEVEN_Z":
                stream_process = files.get_seven_zip_stream_process(local_path)
                data = stream_process.stdout
            else:
                data = files.get_zip_generator(local_path)
            zip_duration = None
        else:
            operation = operations_logger.start_operation(
                OperationName.COMPRESS_OUTPUT, task_id)
            if compress_with == "SEVEN_Z":
                zip_path, zip_duration = files.compress_with_seven_z(local_path)
            else:
                zip_path, zip_duration = files.make_zip_archive(local_path)

            operation.end(attributes={"execution_time_s": zip_duration})

            data = open(zip_path, "rb")

        storage_dir = self._get_storage_dir(task_dir_remote)
        upload_info = self._api_client.get_upload_output_url(storage_dir)

        operation = operations_logger.start_operation(
            OperationName.UPLOAD_OUTPUT, task_id)
        resp, upload_time = WebApiFileManager.upload(upload_info.method,
                                                     upload_info.url, data)
        resp.raise_for_status()

        operation.end(attributes={"execution_time_s": upload_time})

        if stream_zip:
            if compress_with == "SEVEN_Z":
                stream_process.stdout.close()
                stream_process.wait()
                size = int(resp.headers.get("x-goog-stored-content-length"))
            else:
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
        input_resources: list[str],
        dest_path: str,
        workdir: str,
    ):
        files_url = self._api_client.get_download_urls(input_resources)

        for file_url in files_url:
            url = file_url["url"]
            base_path = file_url["file_path"]
            unzip = file_url["unzip"]
            file_path = os.path.join(dest_path, base_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            urllib.request.urlretrieve(url, file_path)

            if unzip:
                extract_to = os.path.join(dest_path, os.path.dirname(file_path))
                files.extract_subfolder_and_cleanup(
                    zip_path=file_path,
                    subfolder="artifacts/",
                    extract_to=extract_to,
                    workdir=workdir,
                )
