"""Database operations for the Scovra agent seed (onyx.scovra.seed)."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.db.models import Persona, StarterMessage, Tool
from onyx.db.persona import get_default_assistant


@dataclass(frozen=True)
class SeededPersonaFields:
    """The persona fields that the Scovra seed owns."""

    name: str
    description: str
    system_prompt: str
    task_prompt: str
    starter_messages: Sequence[StarterMessage]
    icon_name: str
    display_priority: int


def get_seeded_persona_by_id(db_session: Session, persona_id: int) -> Persona | None:
    """Find a persona by id, deleted rows included. A built-in persona never matches,
    so a bad seed state cannot change the default agent."""
    return db_session.scalars(
        select(Persona).where(
            Persona.id == persona_id,
            Persona.builtin_persona.is_(False),
        )
    ).one_or_none()


def get_seedable_persona_by_name(db_session: Session, name: str) -> Persona | None:
    """Find a live, public, ownerless, non-built-in persona with this name.

    A user or a group can own a persona with the same name, so the filter excludes
    owned rows. When more than one row matches, the oldest row wins.
    """
    stmt = (
        select(Persona)
        .where(
            Persona.name == name,
            Persona.user_id.is_(None),
            Persona.owner_group_id.is_(None),
            Persona.builtin_persona.is_(False),
            Persona.is_public.is_(True),
            Persona.deleted.is_(False),
        )
        .order_by(Persona.id)
        .limit(1)
    )
    return db_session.scalars(stmt).first()


def get_tools_by_in_code_tool_ids(
    db_session: Session, in_code_tool_ids: Sequence[str]
) -> dict[str, Tool]:
    """Map each in_code_tool_id to its Tool row. Ids with no row are left out."""
    stmt = (
        select(Tool).where(Tool.in_code_tool_id.in_(in_code_tool_ids)).order_by(Tool.id)
    )
    tools: dict[str, Tool] = {}
    for tool in db_session.scalars(stmt):
        if tool.in_code_tool_id is not None:
            tools.setdefault(tool.in_code_tool_id, tool)
    return tools


def _apply_seeded_fields(
    persona: Persona, fields: SeededPersonaFields, tools: Sequence[Tool]
) -> None:
    persona.name = fields.name
    persona.description = fields.description
    persona.system_prompt = fields.system_prompt
    persona.task_prompt = fields.task_prompt
    persona.replace_base_system_prompt = False
    persona.datetime_aware = True
    persona.starter_messages = list(fields.starter_messages)
    persona.icon_name = fields.icon_name
    persona.display_priority = fields.display_priority
    persona.is_public = True
    persona.is_featured = True
    # No availability check: chat drops unavailable tools at run time
    # (construct_tools), so a tool that becomes available later works with no re-seed.
    persona.tools = list(tools)


def create_seeded_persona(
    db_session: Session, fields: SeededPersonaFields, tools: Sequence[Tool]
) -> Persona:
    """Create an ownerless, public persona. This does not use upsert_persona, because
    its name check also matches personas that users own."""
    persona = Persona(
        user_id=None,
        builtin_persona=False,
        is_listed=True,
        deleted=False,
    )
    _apply_seeded_fields(persona, fields, tools)
    db_session.add(persona)
    db_session.commit()
    return persona


def update_seeded_persona(
    db_session: Session,
    persona: Persona,
    fields: SeededPersonaFields,
    tools: Sequence[Tool],
) -> None:
    _apply_seeded_fields(persona, fields, tools)
    db_session.commit()


def set_default_assistant_starter_messages__no_commit(
    db_session: Session, starter_messages: Sequence[StarterMessage]
) -> None:
    persona = get_default_assistant(db_session)
    if persona is None:
        raise ValueError("Default assistant not found")
    persona.starter_messages = list(starter_messages)
