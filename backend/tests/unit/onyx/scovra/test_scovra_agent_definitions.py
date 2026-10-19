"""Checks of the Scovra agent definitions against the limits of the app."""

import pytest

from onyx.prompts.chat_prompts import DEFAULT_SYSTEM_PROMPT
from onyx.scovra.agents import (
    SCOVRA_AGENTS,
    SCOVRA_DEFAULT_AGENT,
    ScovraAgentDefinition,
)
from onyx.scovra.prompts import SCOVRA_HOUSE_PREAMBLE
from onyx.scovra.seed import DEFAULT_AGENT_STATE_KEY
from onyx.tools.built_in_tools import BUILT_IN_TOOL_MAP
from onyx.tools.tool_implementations.file_reader.file_reader_tool import FileReaderTool

# Keys of agentAvatarIconMap in web/src/refresh-components/avatars/CustomAgentAvatar.tsx
AGENT_AVATAR_ICON_NAMES = {
    "Info",
    "QuestionMark",
    "TextLines",
    "Pen",
    "ClockHands",
    "Hash",
    "Search",
    "Check",
    "BarChart",
    "Activity",
    "File",
    "Image",
    "BooksStack",
    "BooksLine",
    "Terminal",
    "Sliders",
    "AudioEq",
    "Music",
}
# Limits of the agent editor (web/src/lib/constants.ts)
MAX_STARTER_MESSAGES = 4
MAX_CHARACTERS_STARTER_MESSAGE = 200
MAX_CHARACTERS_AGENT_DESCRIPTION = 500


def test_agent_keys_and_names_are_unique() -> None:
    keys = [agent.key for agent in SCOVRA_AGENTS]
    names = [agent.name for agent in SCOVRA_AGENTS]
    assert len(set(keys)) == len(keys)
    assert len(set(names)) == len(names)
    assert DEFAULT_AGENT_STATE_KEY not in keys


@pytest.mark.parametrize("agent", SCOVRA_AGENTS, ids=lambda agent: agent.key)
def test_agent_fits_app_limits(agent: ScovraAgentDefinition) -> None:
    assert agent.icon_name in AGENT_AVATAR_ICON_NAMES
    assert len(agent.description) <= MAX_CHARACTERS_AGENT_DESCRIPTION
    assert 0 < len(agent.starter_messages) <= MAX_STARTER_MESSAGES
    for starter in agent.starter_messages:
        assert 0 < len(starter.message) <= MAX_CHARACTERS_STARTER_MESSAGE
    assert 150 <= len(agent.system_prompt.split()) <= 400
    assert agent.in_code_tool_ids
    for tool_id in agent.in_code_tool_ids:
        assert tool_id in BUILT_IN_TOOL_MAP
    # The OpenSearch stack does not have the file reader tool.
    assert FileReaderTool.__name__ not in agent.in_code_tool_ids


def test_default_agent_prompt_is_house_preamble_then_upstream_prompt() -> None:
    assert SCOVRA_DEFAULT_AGENT.system_prompt == DEFAULT_SYSTEM_PROMPT
    assert DEFAULT_SYSTEM_PROMPT.startswith(SCOVRA_HOUSE_PREAMBLE)
    upstream_part = DEFAULT_SYSTEM_PROMPT.removeprefix(SCOVRA_HOUSE_PREAMBLE)
    assert upstream_part.startswith("You are an expert assistant")
    assert len(SCOVRA_DEFAULT_AGENT.starter_messages) == MAX_STARTER_MESSAGES


def test_definition_hash_changes_with_the_definition() -> None:
    agent = SCOVRA_AGENTS[0]
    assert agent.definition_hash() == agent.definition_hash()
    changed = agent.model_copy(update={"description": agent.description + "."})
    assert changed.definition_hash() != agent.definition_hash()
