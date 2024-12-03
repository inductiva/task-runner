"""Utils for logging operations to the API."""
import datetime
import enum
from typing import Any, Optional

from task_runner import ApiClient, utils


class OperationName(enum.Enum):
    EXEC_COMMAND = "exec_command"
    DOWNLOAD_CONTAINER = "download_container"
    DOWNLOAD_INPUT = "download_input"
    UNCOMPRESS_INPUT = "uncompress_input"
    COMPRESS_OUTPUT = "compress_output"
    UPLOAD_OUTPUT = "upload_output"


@utils.retry()
def _start_operation(
    api_client: ApiClient,
    name: OperationName,
    task_id: str,
    attributes: dict[str, Any],
    timestamp: datetime.datetime,
):
    """Registers a new operation in the API and returns its ID.

    If an exception is raised, the operation is retried until
    it's successful.
    """
    # Since the timestamp that is used is the retrieved by the API,
    # we calculate the elapsed time since the first try of the request,
    # and the API subtracts it from the current time to get the correct
    # timestamp.
    elapsed_since_first_try = (utils.now_utc() - timestamp).total_seconds()

    return api_client.create_operation(
        operation_name=name.value,
        task_id=task_id,
        attributes=attributes,
        timestamp=timestamp,
        elapsed_time_s=elapsed_since_first_try,
    )


@utils.retry()
def _end_operation(
    api_client: ApiClient,
    operation_id: str,
    task_id: str,
    attributes: dict[str, Any],
    timestamp: datetime.datetime,
):
    """Marks an operation as finished in the API."""
    elapsed_since_first_try = (utils.now_utc() - timestamp).total_seconds()

    return api_client.end_operation(
        operation_id=operation_id,
        task_id=task_id,
        attributes=attributes,
        timestamp=timestamp,
        elapsed_time_s=elapsed_since_first_try,
    )


class Operation:
    """Represents an operation, exposing a method to mark it as done."""

    def __init__(
        self,
        api_client: ApiClient,
        name: OperationName,
        task_id: str,
        operation_id: str,
    ):
        self._api_client = api_client
        self._name = name
        self._task_id = task_id
        self._operation_id = operation_id

    def end(
        self,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        attributes = attributes or {}
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        _end_operation(
            self._api_client,
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
        name: OperationName,
        task_id: str,
        attributes: Optional[dict[str, Any]] = None,
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
