"""Client for the Inductiva API."""
import dataclasses
import os
import uuid
from typing import Optional

import requests
from absl import logging


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

    @classmethod
    def from_env(cls):
        return cls(
            api_url=os.getenv("API_URL", "http://web"),
            user_api_key=os.getenv("USER_API_KEY"),
            executer_tracker_token=os.getenv("EXECUTER_TRACKER_TOKEN"),
        )

    def _request(self, method: str, path: str, **kwargs):
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
        resp.raise_for_status()

        return resp

    def register_executer_tracker(self, data) -> ExecuterAccessInfo:
        resp = self._request(
            "POST",
            "/register",
            json=data,
        )
        if resp.status_code != 202:
            raise RuntimeError(
                f"Failed to register executer tracker: {resp.text}")

        resp_body = resp.json()

        return ExecuterAccessInfo(
            id=uuid.UUID(resp_body["executer_tracker_id"]),
            redis_stream=resp_body["redis_stream"],
            redis_consumer_group=resp_body["redis_consumer_group"],
            redis_consumer_name=resp_body["redis_consumer_name"],
            machine_group_id=uuid.UUID(resp_body["machine_group_id"]),
        )

    def kill_machine(self, executer_tracker_id: uuid.UUID) -> int:
        resp = self._request(
            "DELETE",
            f"/{executer_tracker_id}",
        )
        return resp.status_code
