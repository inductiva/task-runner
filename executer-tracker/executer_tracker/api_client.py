"""Client for the Inductiva API."""
import dataclasses
import datetime
import enum
import os
import uuid
from typing import Optional

import requests
from absl import logging


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

        self._url = f"{api_url}/executer-tracker"
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
            api_url=os.getenv("API_URL", "http://web"),
            user_api_key=os.getenv("USER_API_KEY"),
            executer_tracker_token=os.getenv("EXECUTER_TRACKER_TOKEN"),
        )

    def _request(
        self,
        method: str,
        path: str,
        raise_exception: bool = False,
        **kwargs,
    ):
        path = path.lstrip("/")
        url = f"{self._url}/{path}"
        logging.debug("Request: %s %s", method, url)
        resp = requests.request(
            method,
            url,
            **kwargs,
            timeout=self._request_timeout_s,
            headers=self._headers,
        )
        logging.debug("Response:")
        logging.debug(" > status code: %s", resp.status_code)
        logging.debug(" > body: %s", resp.text)

        if raise_exception:
            resp.raise_for_status()

        return resp

    def register_executer_tracker(self, data: dict) -> ExecuterAccessInfo:
        resp = self._request(
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
        resp = self._request(
            "DELETE",
            f"/{self._executer_uuid}",
        )
        return resp.status_code

    def post_task_metric(self, task_id: str, metric: str, value: float):
        data = {
            "timestamp":
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metric":
                metric,
            "value":
                value,
        }

        resp = self._request(
            HTTPMethod.POST.value,
            f"{self._executer_uuid}/task/{task_id}/metric",
            json=data,
        )

        if resp.status_code != 202:
            logging.error("Failed to post task metric: %s", metric)
            logging.info("Response:")
            logging.info(" > status code: %s", resp.status_code)
            logging.info(" > body: %s", resp.text)
