"""Client for the Inductiva API."""
import dataclasses
import datetime
import enum
import os
import time
import urllib
import uuid
from collections import namedtuple
from typing import Any, List, Literal, Optional

import requests
from absl import logging
from inductiva_api import events
from inductiva_api.task_status import TaskRunnerTerminationReason

import task_runner
from task_runner.cleanup import TaskRunnerTerminationError
from task_runner.utils import INPUT_ZIP_FILENAME, OUTPUT_ZIP_FILENAME, host


class HTTPMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class HTTPStatus(enum.Enum):
    SUCCESS = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    CLIENT_ERROR = 400
    INTERNAL_SERVER_ERROR = 500


HTTPResponse = namedtuple("HTTPResponse", ["status", "data"])


@dataclasses.dataclass
class TaskRunnerAccessInfo:
    id: uuid.UUID
    machine_group_id: uuid.UUID


@dataclasses.dataclass
class UploadUrlInfo:
    url: str
    method: str


class ApiClient:
    """Inductiva API client."""

    def __init__(
        self,
        api_url: str,
        user_api_key: str,
        request_timeout_s: int = 300,
    ):
        if user_api_key is None:
            raise RuntimeError("USER_API_KEY must be set.")

        self._url = api_url
        self._request_timeout_s = request_timeout_s
        self._headers = {
            "User-Agent": task_runner.get_api_agent(),
            "X-API-Key": user_api_key,
        }
        self._task_runner_uuid = None

    @classmethod
    def from_env(cls):
        return cls(
            api_url=os.getenv("API_URL", "https://api.inductiva.ai"),
            user_api_key=os.getenv("USER_API_KEY"),
        )

    def _log_response(self, resp: requests.Response):
        logging.debug("Response:")
        logging.debug(" > status code: %s", resp.status_code)
        logging.debug(" > body: %s", resp.text)

    def _request(
        self,
        method: str,
        path: str,
        raise_exception: bool = False,
        **kwargs,
    ):
        url = f"{self._url}/{path.lstrip('/')}"
        logging.debug("Request: %s %s", method, url)
        resp = requests.request(
            method,
            url,
            **kwargs,
            timeout=self._request_timeout_s,
            headers=self._headers,
        )
        self._log_response(resp)

        if raise_exception:
            resp.raise_for_status()

        return resp

    def _request_task_runner_api(self, method: str, path: str, **kwargs):
        full_path = f"/task-runner/{path.lstrip('/')}"

        return self._request(method, full_path, **kwargs)

    def register_task_runner(self, data: dict) -> TaskRunnerAccessInfo:
        resp = self._request_task_runner_api(
            HTTPMethod.POST.value,
            "/register",
            json=data,
        )
        if resp.status_code != HTTPStatus.ACCEPTED.value:
            raise RuntimeError(
                f"Failed to register task runner: {resp.json()['detail']}")

        resp_body = resp.json()

        self._task_runner_uuid = uuid.UUID(resp_body["task_runner_id"])

        return TaskRunnerAccessInfo(
            id=self._task_runner_uuid,
            machine_group_id=uuid.UUID(resp_body["machine_group_id"]),
        )

    def kill_machine(self) -> int:
        resp = self._request_task_runner_api(
            "DELETE",
            f"/{self._task_runner_uuid}",
        )
        return resp.status_code

    def get_task(
        self,
        task_runner_id: uuid.UUID,
        block_s: int,
    ) -> Optional[dict]:
        resp = self._request_task_runner_api(
            "GET",
            f"/{task_runner_id}/task?block_s={block_s}",
        )
        if resp.status_code == HTTPStatus.NO_CONTENT.value:
            return HTTPResponse(HTTPStatus.NO_CONTENT, None)

        if resp.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR.value:
            return HTTPResponse(HTTPStatus.INTERNAL_SERVER_ERROR, None)

        if resp.status_code >= HTTPStatus.CLIENT_ERROR.value:
            raise TaskRunnerTerminationError(
                TaskRunnerTerminationReason.INTERRUPTED,
                detail=resp.json()["detail"])

        return HTTPResponse(HTTPStatus.SUCCESS, resp.json())

    def log_event(
        self,
        task_runner_id: uuid.UUID,
        event: events.Event,
    ):
        return self._request_task_runner_api(
            "POST",
            f"/{task_runner_id}/event",
            json=events.parse.to_dict(event),
            raise_exception=True,
        )

    def receive_task_message(
        self,
        task_runner_id: uuid.UUID,
        task_id: str,
        block_s: int = 30,
    ) -> Optional[str]:
        resp = self._request_task_runner_api(
            "GET",
            f"/{task_runner_id}/task/{task_id}/message?block_s={block_s}",
        )
        if resp.status_code == HTTPStatus.NO_CONTENT.value:
            return HTTPResponse(HTTPStatus.NO_CONTENT, None)

        if resp.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR.value:
            return HTTPResponse(HTTPStatus.INTERNAL_SERVER_ERROR, None)

        return HTTPResponse(HTTPStatus.SUCCESS, resp.json())

    def unblock_task_message_listeners(
        self,
        task_runner_id: uuid.UUID,
        task_id: str,
    ):
        return self._request_task_runner_api(
            "POST",
            f"/{task_runner_id}/task/{task_id}/message/unblock",
        )

    def get_signed_urls(
        self,
        paths: List[str],
        operation: Literal["upload", "download"],
    ) -> List[str]:
        resp = self._request(
            method="GET",
            path="/storage/signed-urls",
            params={
                "paths": paths,
                "operation": operation,
            },
        )
        return resp.json()

    def get_download_input_url(self, storage_dir: str) -> str:
        return self.get_signed_urls(
            paths=[f"{storage_dir}/{INPUT_ZIP_FILENAME}"],
            operation="download",
        )[0]

    def get_upload_output_url(self, storage_dir: str) -> UploadUrlInfo:
        url = self.get_signed_urls(
            paths=[f"{storage_dir}/{OUTPUT_ZIP_FILENAME}"],
            operation="upload",
        )[0]
        return UploadUrlInfo(
            url=url,
            method="PUT",
        )

    def create_local_machine_group(
        self,
        machine_group_name: Optional[str] = None,
    ) -> uuid.UUID:
        resp = self._request(
            "POST",
            "/compute/group",
            json={
                "provider_id":
                    "LOCAL",
                "name":
                    machine_group_name,
                "disk_size_gb":
                    host.get_total_memory() // 1e9,
                "cpu_cores_logical":
                    host.get_cpu_count().logical,
                "cpu_cores_physical":
                    host.get_cpu_count().physical,
                "gpu_count":
                    host.get_gpu_info().count if host.get_gpu_info() else None,
                "gpu_name":
                    host.get_gpu_info().name if host.get_gpu_info() else None,
            },
        )

        if resp.status_code != HTTPStatus.CREATED.value:
            raise RuntimeError(
                f"Failed to create local machine group: {resp.json()}")
        return resp.json()["id"]

    def get_started_machine_group_id_by_name(
            self, machine_group_name: str) -> Optional[uuid.UUID]:
        resp = self._request(
            "GET",
            f"/compute/group/{machine_group_name}",
        )

        if resp.status_code != HTTPStatus.SUCCESS.value:
            return None

        if resp.json()["status"] != "started":
            return None

        return resp.json().get("id")

    def post_task_metric(self, task_id: str, metric: str, value: float):
        data = {"metric": metric, "value": value}
        logging.info("Posting task metric: %s", data)

        max_retries = 5
        retry_interval = 2
        sent = False

        while max_retries > 0 and sent is False:
            resp = self._request_task_runner_api(
                HTTPMethod.POST.value,
                f"{self._task_runner_uuid}/task/{task_id}/metric",
                json=data,
            )

            if resp.status_code == HTTPStatus.ACCEPTED.value:
                sent = True
            else:
                logging.error(
                    "Failed to post task metric: %s, retrying in %s seconds",
                    metric,
                    retry_interval,
                )
                self._log_response(resp)
                time.sleep(retry_interval)

            max_retries -= 1

    def create_operation(
        self,
        operation_name: str,
        task_id: str,
        attributes: dict[str, Any],
        timestamp: Optional[datetime.datetime] = None,
        elapsed_time_s: Optional[float] = None,
    ) -> str:
        """Register a new operation for a given task."""
        timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc)

        resp = self._request_task_runner_api(
            "POST",
            f"{self._task_runner_uuid}/task/{task_id}/operation",
            json={
                "time": timestamp.isoformat(),
                "elapsed_time_s": elapsed_time_s,
                "name": operation_name,
                "attributes": {
                    **attributes,
                },
            },
        )
        resp.raise_for_status()
        return resp.json()["operation_id"]

    def end_operation(
        self,
        operation_id: str,
        task_id: str,
        attributes: dict[str, Any],
        timestamp: Optional[datetime.datetime] = None,
        elapsed_time_s: Optional[float] = None,
    ):
        """Mark an operation as done."""
        timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc)

        resp = self._request_task_runner_api(
            "POST",
            f"{self._task_runner_uuid}/task/{task_id}/operation/{operation_id}/done",
            json={
                "time": timestamp.isoformat(),
                "elapsed_time_s": elapsed_time_s,
                "attributes": {
                    **attributes,
                },
            },
        )
        resp.raise_for_status()

    def get_download_urls(self, input_resources: list[str]) -> str:

        def _signed_url_info(signed_url):
            parsed_url = urllib.parse.urlparse(signed_url)
            path_parts = parsed_url.path.strip(os.sep).split(os.sep)
            _, root_name, *sub_parts = path_parts
            is_output_zip = sub_parts[-1].endswith(OUTPUT_ZIP_FILENAME)
            sub_path = os.sep.join(sub_parts)
            file_path = f"{root_name}/{sub_path}" if is_output_zip else sub_path

            return {
                "url": signed_url,
                "file_path": file_path,
                "unzip": is_output_zip,
            }

        urls = self.get_signed_urls(input_resources, "download")
        return [_signed_url_info(url) for url in urls]
