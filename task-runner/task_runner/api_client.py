"""Client for the Inductiva API."""
import dataclasses
import datetime
import enum
import os
import time
import uuid
from collections import namedtuple
from typing import Any, Optional

import requests
from absl import logging
from inductiva_api import events
from inductiva_api.task_status import TaskRunnerTerminationReason

from task_runner.cleanup import TaskRunnerTerminationError
from task_runner.utils import host


class HTTPMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class HTTPStatus(enum.Enum):
    SUCCESS = 200
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
        user_api_key: Optional[str] = None,
        task_runner_token: Optional[str] = None,
        request_timeout_s: int = 300,
    ):
        if (user_api_key is None) == (task_runner_token is None):
            raise RuntimeError(
                "Exactly one of USER_API_KEY and EXECUTER_TRACKER_TOKEN "
                "should be set.")

        self._url = api_url
        self._request_timeout_s = request_timeout_s
        self._headers = {}
        if user_api_key is not None:
            self._headers["X-API-Key"] = user_api_key
        if task_runner_token is not None:
            self._headers["X-Executer-Tracker-Token"] = task_runner_token
        self._task_runner_uuid = None

    @classmethod
    def from_env(cls):
        return cls(
            api_url=os.getenv("API_URL", "https://api.inductiva.ai"),
            user_api_key=os.getenv("USER_API_KEY"),
            task_runner_token=os.getenv("EXECUTER_TRACKER_TOKEN"),
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
            raise RuntimeError(f"Failed to register task runner: {resp.text}")

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

    def get_download_input_url(
        self,
        task_runner_id: uuid.UUID,
        task_id: str,
    ) -> str:
        resp = self._request_task_runner_api(
            "GET",
            f"/{task_runner_id}/task/{task_id}/download_input_url",
        )

        return resp.json()["url"]

    def get_upload_output_url(
        self,
        task_runner_id: uuid.UUID,
        task_id: str,
    ) -> UploadUrlInfo:
        resp = self._request_task_runner_api(
            "GET",
            f"/{task_runner_id}/task/{task_id}/upload_output_url",
        )

        resp_body = resp.json()

        return UploadUrlInfo(
            url=resp_body["url"],
            method=resp_body["method"],
        )

    def create_local_machine_group(self,
                                   machine_group_name: Optional[str] = None
                                  ) -> uuid.UUID:
        resp = self._request(
            "POST",
            "/compute/group",
            json={
                "provider_id": "LOCAL",
                "name": machine_group_name,
                "disk_size_gb": host.get_total_memory() // 1e9,
            },
        )
        return resp.json()["id"]

    def start_local_machine_group(self, machine_group_id: uuid.UUID):
        resp = self._request(
            "POST",
            "/compute/group/start",
            json={
                "id": machine_group_id,
            },
        )
        return resp.json()["id"]

    def get_machine_group_id_by_name(
            self, machine_group_name: str) -> Optional[uuid.UUID]:
        resp = self._request(
            "GET",
            f"/compute/group/{machine_group_name}",
        )

        if resp.status_code != HTTPStatus.SUCCESS.value:
            return

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

    def get_download_urls(self, input_resources: list[str],
                          task_runner_id: uuid.UUID) -> str:

        resp = self._request_task_runner_api("GET",
                                             f"/{task_runner_id}/download_urls",
                                             params={
                                                 "input_resources":
                                                     input_resources,
                                             })
        response_data = resp.json()
        files_url = [{
            "url": item["url"],
            "file_path": item["file_path"],
        } for item in response_data]

        return files_url
