"""Client for the Inductiva API."""
import dataclasses
import datetime
import enum
import os
import urllib
import uuid
from collections import namedtuple
from typing import Any, List, Literal, Optional

import requests
import tenacity
from absl import logging

import task_runner
from task_runner import events
from task_runner.cleanup import TaskRunnerTerminationError
from task_runner.task_status import TaskRunnerTerminationReason
from task_runner.utils import INPUT_ZIP_FILENAME, OUTPUT_ZIP_FILENAME, host

HTTP_REQUEST_MAX_ATTEMPTS = 5


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
    max_idle_time: Optional[int] = None


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

    def _single_request(
        self,
        method: str,
        path: str,
        raise_exception: bool = False,
        timeout: Optional[int] = None,
        **kwargs,
    ):
        url = f"{self._url}/{path.lstrip('/')}"
        logging.debug("Request: %s %s", method, url)
        timeout = timeout or self._request_timeout_s

        response = requests.request(
            method,
            url,
            timeout=timeout,
            headers=self._headers,
            **kwargs,
        )
        logging.debug("Response:")
        logging.debug(" > status code: %s", response.status_code)
        logging.debug(" > body: %s", response.text)

        if raise_exception:
            response.raise_for_status()

        return response

    def _request(
        self,
        method: str,
        path: str,
        raise_exception: bool = False,
        timeout: Optional[int] = None,
        attempts: int = 1,
        exponential_backoff_multiplier: float = 2.0,
        **kwargs,
    ):
        for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_attempt(attempts),
                wait=tenacity.wait_exponential(
                    multiplier=exponential_backoff_multiplier),
                reraise=raise_exception,
        ):
            with attempt:
                return self._single_request(
                    method=method,
                    path=path,
                    raise_exception=raise_exception,
                    timeout=timeout,
                    **kwargs,
                )

    def _request_task_runner_api(
        self,
        method: str,
        path: str,
        raise_exception: bool = False,
        timeout: Optional[int] = None,
        attempts: int = 1,
        exponential_backoff_multiplier: float = 2.0,
        **kwargs,
    ):
        full_path = f"/task-runner/{path.lstrip('/')}"

        return self._request(
            method,
            full_path,
            raise_exception,
            timeout,
            attempts,
            exponential_backoff_multiplier,
            **kwargs,
        )

    def register_task_runner(self, data: dict) -> TaskRunnerAccessInfo:
        resp = self._request_task_runner_api(
            method=HTTPMethod.POST.value,
            path="/register",
            json=data,
        )
        if resp.status_code != HTTPStatus.ACCEPTED.value:
            raise RuntimeError(
                f"Failed to register task runner: {resp.json()['detail']}")

        resp_body = resp.json()

        self._task_runner_uuid = uuid.UUID(resp_body["task_runner_id"])

        return TaskRunnerAccessInfo(id=self._task_runner_uuid,
                                    machine_group_id=uuid.UUID(
                                        resp_body["machine_group_id"]))

    def kill_machine(self) -> int:
        resp = self._request_task_runner_api(
            method=HTTPMethod.DELETE.value,
            path=f"/{self._task_runner_uuid}",
        )
        return resp.status_code

    def get_task(
        self,
        task_runner_id: uuid.UUID,
        block_s: int,
    ) -> Optional[dict]:
        resp = self._request_task_runner_api(
            method=HTTPMethod.GET.value,
            path=f"/{task_runner_id}/task?block_s={block_s}",
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
            method=HTTPMethod.POST.value,
            path=f"/{task_runner_id}/event",
            attempts=HTTP_REQUEST_MAX_ATTEMPTS,
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
            method=HTTPMethod.GET.value,
            path=f"/{task_runner_id}/task/{task_id}/message?block_s={block_s}",
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
            method=HTTPMethod.POST.value,
            path=f"/{task_runner_id}/task/{task_id}/message/unblock",
        )

    def get_signed_urls(
        self,
        paths: List[str],
        operation: Literal["upload", "download"],
    ) -> List[str]:
        resp = self._request(
            method="GET",
            path="/storage/signed-urls",
            raise_exception=True,
            attempts=HTTP_REQUEST_MAX_ATTEMPTS,
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

    def get_upload_output_url(
            self,
            storage_dir: str,
            output_filename: Optional[str] = None) -> UploadUrlInfo:
        output_filename = output_filename or OUTPUT_ZIP_FILENAME
        url = self.get_signed_urls(
            paths=[f"{storage_dir}/{output_filename}"],
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
            method=HTTPMethod.POST.value,
            path="/compute/group",
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
                "max_idle_time": (int(os.getenv("MAX_IDLE_TIMEOUT"))
                                  if os.getenv("MAX_IDLE_TIMEOUT") else None)
            },
        )

        if resp.status_code != HTTPStatus.CREATED.value:
            raise RuntimeError(
                f"Failed to create local machine group: {resp.json()}")
        return resp.json()["id"]

    def delete_machine_group(self, machine_group_id: uuid.UUID) -> int:
        """Delete a machine group.
        
        Args:
            machine_group_id: UUID of the machine group to delete
            
        Returns:
            HTTP status code of the delete request
        """
        resp = self._request(
            method=HTTPMethod.DELETE.value,
            path="/compute/group",
            params={"machine_group_id": str(machine_group_id)},
        )
        return resp.status_code

    def get_started_machine_group_by_name(
            self, machine_group_name: str) -> Optional[dict]:
        resp = self._request(
            method="GET",
            path=f"/compute/group/{machine_group_name}",
        )

        if resp.status_code != HTTPStatus.SUCCESS.value:
            return None

        machine_group_data = resp.json()
        if machine_group_data["status"] != "started":
            return None

        return {
            "id": machine_group_data.get("id"),
            "max_idle_time": machine_group_data.get("max_idle_time")
        }

    def post_task_metric(self, task_id: str, metric: str, value: float):
        data = {"metric": metric, "value": value}
        logging.info("Posting task metric: %s", data)

        self._request_task_runner_api(
            method=HTTPMethod.POST.value,
            path=f"{self._task_runner_uuid}/task/{task_id}/metric",
            attempts=HTTP_REQUEST_MAX_ATTEMPTS,
            json=data,
        )

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
            method=HTTPMethod.POST.value,
            path=f"{self._task_runner_uuid}/task/{task_id}/operation",
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
            method=HTTPMethod.POST.value,
            path=
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
