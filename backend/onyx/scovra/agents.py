"""Code definitions of the Scovra agents and of the default agent configuration.

The seed (`onyx.scovra.seed`) writes these definitions to the database. A change to a
definition changes its hash, and the next api_server start applies it again.
"""

import hashlib
import json

from pydantic import BaseModel, ConfigDict

from onyx.db.models import StarterMessage
from onyx.prompts.chat_prompts import DEFAULT_SYSTEM_PROMPT
from onyx.scovra.prompts import (
    GRANT_WRITER_SYSTEM_PROMPT,
    OUTREACH_SYSTEM_PROMPT,
    REPORTING_SYSTEM_PROMPT,
    SCOUT_SYSTEM_PROMPT,
)
from onyx.tools.tool_implementations.memory.memory_tool import MemoryTool
from onyx.tools.tool_implementations.open_url.open_url_tool import OpenURLTool
from onyx.tools.tool_implementations.python.python_tool import PythonTool
from onyx.tools.tool_implementations.search.search_tool import SearchTool
from onyx.tools.tool_implementations.web_search.web_search_tool import WebSearchTool


def _definition_hash(definition: BaseModel) -> str:
    # Canonical JSON (sorted keys, fixed separators), so the hash does not change
    # with the field order or with the pydantic serializer version.
    canonical = json.dumps(
        definition.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _starters(*messages: str) -> list[StarterMessage]:
    # The agent editor stores each starter with name equal to message.
    return [StarterMessage(name=message, message=message) for message in messages]


class ScovraAgentDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Stable key in the seed state. Do not change it after a release.
    key: str
    name: str
    description: str
    system_prompt: str
    task_prompt: str = ""
    starter_messages: list[StarterMessage]
    # A key of agentAvatarIconMap in web/src/refresh-components/avatars/CustomAgentAvatar.tsx
    icon_name: str
    display_priority: int
    # Tool.in_code_tool_id values (built-in tool class names)
    in_code_tool_ids: list[str]

    def definition_hash(self) -> str:
        return _definition_hash(self)


class ScovraDefaultAgentDefinition(BaseModel):
    """The parts of the default agent (persona 0) that Scovra sets. Its tools are
    not part of it: admins manage them."""

    model_config = ConfigDict(frozen=True)

    system_prompt: str
    starter_messages: list[StarterMessage]

    def definition_hash(self) -> str:
        return _definition_hash(self)


SCOUT_AGENT = ScovraAgentDefinition(
    key="scout",
    name="Scout",
    description=(
        "Finds grants and other funding that fit your organization. Checks "
        "eligibility, deadlines, award size, and match, and gives a ranked "
        "shortlist with sources."
    ),
    system_prompt=SCOUT_SYSTEM_PROMPT,
    starter_messages=_starters(
        "Find federal grants for youth workforce programs in Ohio that close in the next 90 days",
        "Check if we are eligible for a specific NOFO",
        "Shortlist family foundations that fund food security in Texas",
        "Summarize a foundation's recent giving from its 990-PF",
    ),
    icon_name="Search",
    display_priority=1,
    in_code_tool_ids=[
        WebSearchTool.__name__,
        OpenURLTool.__name__,
        SearchTool.__name__,
        MemoryTool.__name__,
    ],
)

GRANT_WRITER_AGENT = ScovraAgentDefinition(
    key="grant_writer",
    name="Grant Writer",
    description=(
        "Turns a NOFO or RFP into an outline and a compliance checklist, drafts "
        "sections from your own documents, builds budgets, and scores drafts "
        "against the review criteria."
    ),
    system_prompt=GRANT_WRITER_SYSTEM_PROMPT,
    starter_messages=_starters(
        "Turn a NOFO into an outline and a compliance checklist",
        "Draft a Statement of Need from our latest annual report",
        "Build a 12-month budget for a $150,000 request",
        "Score my draft against the funder's review criteria",
    ),
    icon_name="Pen",
    display_priority=2,
    in_code_tool_ids=[
        SearchTool.__name__,
        PythonTool.__name__,
        OpenURLTool.__name__,
        WebSearchTool.__name__,
        MemoryTool.__name__,
    ],
)

OUTREACH_AGENT = ScovraAgentDefinition(
    key="outreach",
    name="Outreach",
    description=(
        "Drafts funder emails, letters of inquiry, follow-ups, thank-you notes, "
        "and meeting briefs. Your team reviews and sends every message."
    ),
    system_prompt=OUTREACH_SYSTEM_PROMPT,
    starter_messages=_starters(
        "Draft an intro email to a foundation program officer",
        "Prepare a brief for my next call with a funder",
        "Write a follow-up after three weeks with no reply",
        "Draft a one-page letter of inquiry",
    ),
    icon_name="TextLines",
    display_priority=3,
    in_code_tool_ids=[
        SearchTool.__name__,
        WebSearchTool.__name__,
        OpenURLTool.__name__,
        MemoryTool.__name__,
    ],
)

REPORTING_AGENT = ScovraAgentDefinition(
    key="reporting",
    name="Reporting",
    description=(
        "Extracts requirements and deadlines from award letters, tracks what is "
        "due, and drafts progress and financial reports with the numbers "
        "calculated."
    ),
    system_prompt=REPORTING_SYSTEM_PROMPT,
    starter_messages=_starters(
        "Extract the deadlines and deliverables from an award letter",
        "Draft a quarterly progress report from our outcomes data",
        "What reports and deliverables are due in the next 30 days?",
        "Summarize budget vs. actuals variance for a grant",
    ),
    icon_name="BarChart",
    display_priority=4,
    in_code_tool_ids=[
        SearchTool.__name__,
        PythonTool.__name__,
        OpenURLTool.__name__,
        MemoryTool.__name__,
    ],
)

SCOVRA_AGENTS: list[ScovraAgentDefinition] = [
    SCOUT_AGENT,
    GRANT_WRITER_AGENT,
    OUTREACH_AGENT,
    REPORTING_AGENT,
]

# DEFAULT_SYSTEM_PROMPT starts with the Scovra house preamble.
SCOVRA_DEFAULT_AGENT = ScovraDefaultAgentDefinition(
    system_prompt=DEFAULT_SYSTEM_PROMPT,
    starter_messages=_starters(
        "Find funding opportunities that fit our programs",
        "What must we have in place to apply for federal grants?",
        "Help me plan our grant calendar for the next six months",
        "Draft a thank-you note to a funder after an award",
    ),
)
