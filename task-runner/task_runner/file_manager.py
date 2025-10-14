import abc
import os
import pathlib
import traceback
import urllib
import urllib.request
import uuid
from typing import Optional

import requests
import tenacity
from absl import logging
from typing_extensions import override

import task_runner
from task_runner import utils
from task_runner.operations_logger import OperationName, OperationsLogger
from task_runner.utils import files


class BaseFileManager(abc.ABC):

    @abc.abstractmethod
    def download_input(
        self,
        task_dir_remote: str,
        region: Optional[str],
        dest_path: str,
    ):
        pass

    @abc.abstractmethod
    def upload_output(
        self,
        task_id: str,
        task_dir_remote: str,
        region: Optional[str],
        local_path: str,
        task_runner_uuid: uuid.UUID,
        operations_logger: OperationsLogger,
        stream_zip: bool = True,
        compress_with: str = "AUTO",
        output_filename: Optional[str] = None,
    ):
        pass

    @abc.abstractmethod
    def download_input_resources(
        self,
        input_resources: list[str],
        region: Optional[str],
        dest_path: str,
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
        task_dir_remote: str,
        region: Optional[str],
        dest_path: str,
    ):
        """Download input zip from remote storage.

        Args:
            task_dir_remote: Input remote path.
            region: Remote storage region.
            dest_path: Local path where the files will be stored.
        """
        storage_dir = self._get_storage_dir(task_dir_remote)
        url = self._api_client.get_download_input_url(storage_dir, region)
        urllib.request.urlretrieve(url, dest_path)

    @staticmethod
    def upload(method: str, url: str, data) -> requests.Response:
        response = requests.request(
            method=method,
            url=url,
            data=data,
            timeout=WebApiFileManager.REQUEST_TIMEOUT_S,
            headers={"Content-Type": "application/octet-stream"},
        )
        logging.info(
            "Upload Response. Status: %s, Body: %s",
            response.status_code,
            response.text,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def before_sleep(retry_state: tenacity.RetryCallState, task_id: str,
                     task_runner_uuid: uuid.UUID) -> None:
        error = retry_state.outcome.exception()
        if error is None:
            return

        message = utils.get_exception_root_cause_message(error)
        logging.error(
            "Output upload failed for task %s on runner %s (retry %d): %s\n%s",
            task_id,
            task_runner_uuid,
            retry_state.attempt_number,
            message,
            traceback.format_exc(),
        )

    @staticmethod
    @utils.execution_time_with_result
    def retry_upload(
        method: str,
        url: str,
        data,
        task_id: str,
        task_runner_uuid: uuid.UUID,
        max_attempt_number: int = 5,
        multiplier: int = 10,
    ) -> requests.Response:
        for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_attempt(max_attempt_number),
                wait=tenacity.wait_exponential(multiplier),
                before_sleep=lambda retry_state: WebApiFileManager.before_sleep(
                    retry_state, task_id, task_runner_uuid),
                reraise=True,
        ):
            with attempt:
                return WebApiFileManager.upload(method, url, data)

    @override
    def upload_output(
        self,
        task_id: str,
        task_dir_remote: str,
        region: Optional[str],
        local_path: str,
        task_runner_uuid: uuid.UUID,
        operations_logger: OperationsLogger,
        stream_zip: bool = True,
        compress_with: str = "AUTO",
        output_filename: Optional[str] = None,
    ):
        """Upload output zip to remote storage.

        Args:
            task_id: Task ID.
            task_dir_remote: Remote path where the output will be stored.
            region: Remote storage region.
            local_path: Local path where the output files are stored.
            task_runner_uuid: Task-runner UUID.
            operations_logger: Operations logger instance.
            stream_zip: If True, the output will be streamed as it is being
                compressed. If False, the output will be compressed first, and
                then uploaded.
            compress_with: Compression method to use.
            output_filename: Name of the output file. If None, the default
                value will be used.
        """
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
        upload_info = self._api_client.get_upload_output_url(
            storage_dir, region, output_filename)

        operation = operations_logger.start_operation(
            OperationName.UPLOAD_OUTPUT, task_id)
        resp, upload_time = WebApiFileManager.retry_upload(
            method=upload_info.method,
            url=upload_info.url,
            data=data,
            task_id=task_id,
            task_runner_uuid=task_runner_uuid,
        )

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
        region: Optional[str],
        dest_path: str,
        workdir: str,
    ):
        """Download input resources from remote storage.

        Args:
            input_resources: List of files to download.
            region: Remote storage region.
            dest_path: Local path where the files will be stored.
            workdir: The working directory.
        """
        files_url = self._api_client.get_download_urls(input_resources, region)

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
