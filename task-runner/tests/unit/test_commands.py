"""Test the the command class."""

import pytest
from task_runner import executers


def test_empty_command():
    """Test empty command."""
    with pytest.raises(ValueError):
        executers.Command("")


def test_long_command():
    """Test long command."""
    with pytest.raises(ValueError):
        executers.Command("a" * 257)
