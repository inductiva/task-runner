"""Mapping of API simulators to the Executer classes that 
perform those simulations."""
from typing import Optional

from task_runner import executers

simulator_to_executer = {
    "arbitrary_commands":
        executers.arbitrary_commands_executer.ArbitraryCommandsExecuter,
}


def get_executer(simulator: str) -> Optional[type[executers.BaseExecuter]]:
    """Get the Executer class for the given API method.

    Args:
        api_method: The API method to get the Executer class for.

    Returns:
        The Executer class that performs the given API method.
    """
    return simulator_to_executer.get(simulator)
