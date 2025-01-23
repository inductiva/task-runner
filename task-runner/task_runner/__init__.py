# noqa: D104
from task_runner.api_client import (
    ApiClient,
    HTTPStatus,
)
from task_runner.api_file_tracker import ApiFileTracker
from task_runner.event_logger import (
    BaseEventLogger,
    WebApiLogger,
)
from task_runner.file_manager import (
    BaseFileManager,
    WebApiFileManager,
)
from task_runner.machine_group import MachineGroupInfo
from task_runner.task_fetcher import (
    BaseTaskFetcher,
    WebApiTaskFetcher,
)
from task_runner.task_message_listener import (
    BaseTaskMessageListener,
    WebApiTaskMessageListener,
)
from task_runner.task_request_handler import TaskRequestHandler

__version__ = "0.1.0"


def get_api_agent():
    return f"TaskRunner/{__version__}/python"
