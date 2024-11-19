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
    """Registers a new operation in the API and returns its ID.

    If an exception is raised, the operation is retried until
    it's successful.
    """
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
    """Marks an operation as finished in the API."""
    return api_client.end_operation(
        operation_name=name,
        operation_id=operation_id,
        task_id=task_id,
        attributes=attributes,
        timestamp=timestamp,
    )


class Operation:
    """Represents an operation, exposing a method to mark it as done."""

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
    """Util class to log operations to the API.

    It provides a method to start a new operation, which returns an
    Operation instance. This istance can be used to mark the operation
    as done.

    Example:
        operations_logger = OperationsLogger(api_client)

        operation = operations_logger.start_operation(
            name="my_operation",
            task_id="my_task",
            attributes={
                "key": "value",
            },
        )
        # code that performs the operation
        ...
        #
        operation.end(
            attributes={
                "key": "value",
            },
        )
    """

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
