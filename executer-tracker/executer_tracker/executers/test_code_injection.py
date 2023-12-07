"""Test the robustness of the command class against code injection attacks."""

import pytest

from executer_tracker import executers


class TestCommand(executers.Command):
    """Dummy command class."""

    def check_security(self, cmd, prompts):
        executers.Command.check_security(cmd, prompts)
        pass


def test_empty_command():
    """Test empty command."""
    with pytest.raises(ValueError):
        TestCommand("")


def test_long_command():
    """Test long command."""
    with pytest.raises(ValueError):
        TestCommand("a" * 257)


@pytest.mark.parametrize("cmd", [
    "gmx protein.gro; rm -rf /",
    "gmx proten.gro && rm -rf /",
    "gmx proten.gro | rm -rf /",
])
def test_command_concatenation_operator_characters(cmd):
    """Test command concatenation operator characters."""
    with pytest.raises(ValueError):
        TestCommand(cmd)


@pytest.mark.parametrize("prompts", [
    ["value; rm -rf /"],
    ["value && rm -rf /"],
    ["value | rm -rf /"],
])
def test_prompt_invalid_characters(prompts):
    """Test invalid characters in prompts."""
    with pytest.raises(ValueError):
        TestCommand("gmx protein.gro", prompts)


@pytest.mark.parametrize("cmd, prompts", [
    ("gmx pdb2gmx -f protein.pdb", ["amber94"]),
    ("gmx pdb2gmx -f protein.pdb", ["amber94", "system"]),
    ("gmx pdb2gmx -f protein.pdb -o protein_output.gro", ["amber94", "system"]),
    ("gmx pdb2gmx -f", ["amber94", "system"])
])
def test_valid_init(cmd, prompts):
    """Test valid initialization."""
    command = TestCommand(cmd, prompts)

    assert command.cmd == cmd
    assert command.prompts == prompts
