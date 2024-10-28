"""Utils for logging operations to the API."""
import datetime
from typing import Any, Dict, Optional

from task_runner import ApiClient, utils


@utils.retry()
def _start_operation(
    api_client: ApiClient,
    name: str,
    task_id: str,
    attributes: Dict[str, Any],
    timestamp: datetime.datetime,
):
    return api_client.create_operation(
        operation_name=name,
        task_id=task_id,
        attributes=attributes,
        timestamp=timestamp,
    )


@utils.retry()
def _end_operation(
    api_client: ApiClient,
    name: str,
    operation_id: str,
    task_id: str,
    attributes: Dict[str, Any],
    timestamp: datetime.datetime,
):
    return api_client.end_operation(
        operation_name=name,
        operation_id=operation_id,
        task_id=task_id,
        attributes=attributes,
        timestamp=timestamp,
    )


class Operation:

    def __init__(
        self,
        api_client: ApiClient,
        name: str,
        task_id: str,
        operation_id: str,
    ):
        self._api_client = api_client
        self._name = name
        self._task_id = task_id
        self._operation_id = operation_id

    def end(
        self,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        attributes = attributes or {}
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        _end_operation(
            self._api_client,
            self._name,
            self._operation_id,
            self._task_id,
            attributes,
            timestamp,
        )


class OperationsLogger:

    def __init__(
        self,
        api_client: ApiClient,
    ):
        self._api_client = api_client

    def start_operation(
        self,
        name: str,
        task_id: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Operation:
        attributes = attributes or {}
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        operation_id = _start_operation(
            self._api_client,
            name,
            task_id,
            attributes,
            timestamp,
        )

        return Operation(self._api_client, name, task_id, operation_id)
