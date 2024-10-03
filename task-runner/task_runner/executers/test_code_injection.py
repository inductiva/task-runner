"""Test the robustness of the command class against code injection attacks."""

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


@pytest.mark.parametrize("cmd", [
    "gmx protein.gro; rm -rf /",
    "gmx proten.gro && rm -rf /",
    "gmx proten.gro | rm -rf /",
])
def test_command_concatenation_operator_characters(cmd):
    """Test command concatenation operator characters."""
    with pytest.raises(ValueError):
        executers.Command(cmd)


@pytest.mark.parametrize("prompts", [
    ["value; rm -rf /"],
    ["value && rm -rf /"],
    ["value | rm -rf /"],
])
def test_prompt_invalid_characters(prompts):
    """Test invalid characters in prompts."""
    with pytest.raises(ValueError):
        executers.Command("gmx protein.gro", prompts)
