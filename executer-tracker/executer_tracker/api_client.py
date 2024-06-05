"""Client for the Inductiva API."""
import dataclasses
import enum
import os
import time
import uuid
from typing import Dict, Optional

import requests
from absl import logging

from inductiva_api import events


class HTTPMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


@dataclasses.dataclass
class ExecuterAccessInfo:
    id: uuid.UUID
    redis_stream: str
    redis_consumer_group: str
    redis_consumer_name: str
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
        executer_tracker_token: Optional[str] = None,
        request_timeout_s: int = 300,
    ):
        if (user_api_key is None) == (executer_tracker_token is None):
            raise RuntimeError(
                "Exactly one of USER_API_KEY and EXECUTER_TRACKER_TOKEN "
                "should be set.")

        self._url = api_url
        self._request_timeout_s = request_timeout_s
        self._headers = {}
        if user_api_key is not None:
            self._headers["X-API-Key"] = user_api_key
        if executer_tracker_token is not None:
            self._headers["X-Executer-Tracker-Token"] = executer_tracker_token
        self._executer_uuid = None

    @classmethod
    def from_env(cls):
        return cls(
            api_url=os.getenv("API_URL", "https://api.inductiva.ai"),
            user_api_key=os.getenv("USER_API_KEY"),
            executer_tracker_token=os.getenv("EXECUTER_TRACKER_TOKEN"),
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

    def _request_executer_tracker_api(self, method: str, path: str, **kwargs):
        full_path = f"/executer-tracker/{path.lstrip('/')}"

        return self._request(method, full_path, **kwargs)

    def register_executer_tracker(self, data: dict) -> ExecuterAccessInfo:
        resp = self._request_executer_tracker_api(
            HTTPMethod.POST.value,
            "/register",
            json=data,
        )
        if resp.status_code != 202:
            raise RuntimeError(
                f"Failed to register executer tracker: {resp.text}")

        resp_body = resp.json()

        self._executer_uuid = uuid.UUID(resp_body["executer_tracker_id"])

        return ExecuterAccessInfo(
            id=self._executer_uuid,
            redis_stream=resp_body["redis_stream"],
            redis_consumer_group=resp_body["redis_consumer_group"],
            redis_consumer_name=resp_body["redis_consumer_name"],
            machine_group_id=uuid.UUID(resp_body["machine_group_id"]),
        )

    def kill_machine(self) -> int:
        resp = self._request_executer_tracker_api(
            "DELETE",
            f"/{self._executer_uuid}",
        )
        return resp.status_code

    def get_task(
        self,
        executer_tracker_id: uuid.UUID,
        block_s: int,
    ) -> Optional[Dict]:
        resp = self._request_executer_tracker_api(
            "GET",
            f"/{executer_tracker_id}/task?block_s={block_s}",
        )
        if resp.status_code == 204:
            return None

        return resp.json()

    def acknowledge_task(
        self,
        executer_tracker_id: uuid.UUID,
        task_id: str,
    ):
        return self._request_executer_tracker_api(
            "POST",
            f"/{executer_tracker_id}/task/{task_id}/ack",
        )

    def log_event(
        self,
        executer_tracker_id: uuid.UUID,
        event: events.Event,
    ):
        return self._request_executer_tracker_api(
            "POST",
            f"/{executer_tracker_id}/event",
            json=events.parse.to_dict(event),
        )

    def receive_task_message(
        self,
        executer_tracker_id: uuid.UUID,
        task_id: str,
        block_s: int = 30,
    ) -> Optional[str]:
        resp = self._request_executer_tracker_api(
            "GET",
            f"/{executer_tracker_id}/task/{task_id}/message?block_s={block_s}",
        )
        if resp.status_code == 204:
            return None

        return resp.json()

    def unblock_task_message_listeners(
        self,
        executer_tracker_id: uuid.UUID,
        task_id: str,
    ):
        return self._request_executer_tracker_api(
            "POST",
            f"/{executer_tracker_id}/task/{task_id}/message/unblock",
        )

    def get_download_input_url(
        self,
        executer_tracker_id: uuid.UUID,
        task_id: str,
    ) -> str:
        resp = self._request_executer_tracker_api(
            "GET",
            f"/{executer_tracker_id}/task/{task_id}/download_input_url",
        )

        return resp.json()["url"]

    def get_upload_output_url(
        self,
        executer_tracker_id: uuid.UUID,
        task_id: str,
    ) -> UploadUrlInfo:
        resp = self._request_executer_tracker_api(
            "GET",
            f"/{executer_tracker_id}/task/{task_id}/upload_output_url",
        )

        resp_body = resp.json()

        return UploadUrlInfo(
            url=resp_body["url"],
            method=resp_body["method"],
        )

    def create_local_machine_group(self) -> uuid.UUID:
        resp = self._request(
            "POST",
            "/compute/group",
            json={
                "provider_id": "LOCAL",
            },
        )
        return resp.json()["id"]

    def post_task_metric(self, task_id: str, metric: str, value: float):
        data = {"metric": metric, "value": value}
        logging.info("Posting task metric: %s", data)

        max_retries = 5
        retry_interval = 2
        sent = False

        while max_retries > 0 and sent is False:
            resp = self._request_executer_tracker_api(
                HTTPMethod.POST.value,
                f"{self._executer_uuid}/task/{task_id}/metric",
                json=data,
            )

            if resp.status_code == 202:
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
