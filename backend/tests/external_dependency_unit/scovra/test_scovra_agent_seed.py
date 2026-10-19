"""External dependency tests for the Scovra agent seed (onyx.scovra.seed).

They need Postgres with migrations applied. Use a separate database, for example:

    cd backend && POSTGRES_DB=scovra_test POSTGRES_PORT=5434 uv run alembic upgrade head
    cd backend && POSTGRES_DB=scovra_test POSTGRES_PORT=5434 \
        uv run pytest tests/external_dependency_unit/scovra
"""

from collections.abc import Generator, Sequence
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import null, select, update
from sqlalchemy.orm import Session

from onyx.db.models import Persona, StarterMessage, Tool, UserGroup
from onyx.db.persona import get_default_assistant
from onyx.db.scovra import SeededPersonaFields
from onyx.key_value_store.factory import get_kv_store
from onyx.key_value_store.interface import KvKeyNotFoundError
from onyx.prompts.chat_prompts import DEFAULT_SYSTEM_PROMPT
from onyx.scovra import seed as seed_module
from onyx.scovra.agents import (
    SCOUT_AGENT,
    SCOVRA_AGENTS,
    SCOVRA_DEFAULT_AGENT,
    ScovraAgentDefinition,
)
from onyx.scovra.prompts import SCOVRA_HOUSE_PREAMBLE
from onyx.scovra.seed import (
    SCOVRA_SEED_STATE_KEY,
    AgentSeedRecord,
    ScovraSeedState,
    seed_scovra_agents,
)
from onyx.tools.tool_implementations.python.python_tool import PythonTool
from onyx.tools.tool_implementations.search.search_tool import SearchTool
from onyx.tools.tool_implementations.web_search.web_search_tool import WebSearchTool
from tests.external_dependency_unit.conftest import create_test_user, delete_test_user

SEEDED_NAMES: list[str] = [agent.name for agent in SCOVRA_AGENTS]


def _delete_seed_state() -> None:
    try:
        get_kv_store().delete(SCOVRA_SEED_STATE_KEY)
    except KvKeyNotFoundError:
        pass


def _load_seed_state() -> ScovraSeedState:
    return ScovraSeedState.from_json(
        get_kv_store().load(SCOVRA_SEED_STATE_KEY, refresh_cache=True)
    )


def _delete_ownerless_seed_personas(db_session: Session) -> None:
    personas = db_session.scalars(
        select(Persona).where(
            Persona.name.in_(SEEDED_NAMES),
            Persona.user_id.is_(None),
            Persona.owner_group_id.is_(None),
            Persona.builtin_persona.is_(False),
        )
    ).all()
    for persona in personas:
        persona.tools = []
        db_session.delete(persona)
    db_session.commit()


def _live_seeded_personas(db_session: Session) -> dict[str, Persona]:
    db_session.expire_all()
    personas = db_session.scalars(
        select(Persona).where(
            Persona.name.in_(SEEDED_NAMES),
            Persona.user_id.is_(None),
            Persona.owner_group_id.is_(None),
            Persona.builtin_persona.is_(False),
            Persona.deleted.is_(False),
        )
    ).all()
    by_name: dict[str, Persona] = {}
    for persona in personas:
        assert persona.name not in by_name, f"duplicate seeded agent {persona.name}"
        by_name[persona.name] = persona
    return by_name


def _in_code_tool_ids(persona: Persona) -> set[str]:
    return {
        tool.in_code_tool_id
        for tool in persona.tools
        if tool.in_code_tool_id is not None
    }


def _assert_matches_definition(
    persona: Persona, definition: ScovraAgentDefinition
) -> None:
    assert persona.description == definition.description
    assert persona.system_prompt == definition.system_prompt
    assert persona.task_prompt == definition.task_prompt
    assert persona.starter_messages == definition.starter_messages
    assert persona.icon_name == definition.icon_name
    assert persona.display_priority == definition.display_priority
    assert persona.is_public is True
    assert persona.is_featured is True
    assert persona.datetime_aware is True
    assert persona.replace_base_system_prompt is False
    assert _in_code_tool_ids(persona) == set(definition.in_code_tool_ids)


# Columns of the default agent that the seed, or a bug in it, can change.
DEFAULT_AGENT_COLUMNS: list[str] = [
    "name",
    "description",
    "system_prompt",
    "task_prompt",
    "starter_messages",
    "icon_name",
    "display_priority",
    "is_public",
    "is_featured",
    "is_listed",
    "datetime_aware",
    "replace_base_system_prompt",
    "deleted",
]


@pytest.fixture(autouse=True)
def clean_scovra_seed(db_session: Session) -> Generator[None, None, None]:
    """Start each test with no Scovra agents and no seed state, and restore the
    default agent afterwards."""
    default_agent = get_default_assistant(db_session)
    assert default_agent is not None, "migrations create the default agent"
    default_agent_id = default_agent.id
    persona_table = Persona.__table__
    original_values: dict[str, Any] = dict(
        db_session.execute(
            select(
                *[persona_table.c[column] for column in DEFAULT_AGENT_COLUMNS]
            ).where(persona_table.c.id == default_agent_id)
        )
        .one()
        ._mapping
    )
    original_tool_ids = [tool.id for tool in default_agent.tools]

    _delete_seed_state()
    _delete_ownerless_seed_personas(db_session)
    try:
        yield
    finally:
        db_session.rollback()
        _delete_seed_state()
        _delete_ownerless_seed_personas(db_session)
        # null() writes SQL NULL; None would write JSON null to the JSONB column.
        db_session.execute(
            update(Persona)
            .where(Persona.id == default_agent_id)
            .values(
                {
                    column: null() if value is None else value
                    for column, value in original_values.items()
                }
            )
        )
        db_session.expire_all()
        default_agent = db_session.get(Persona, default_agent_id)
        assert default_agent is not None
        default_agent.tools = list(
            db_session.scalars(select(Tool).where(Tool.id.in_(original_tool_ids)))
        )
        db_session.commit()


def test_first_seed_creates_agents_with_tools_even_when_unavailable(
    db_session: Session,
) -> None:
    with (
        patch.object(SearchTool, "is_available", return_value=False),
        patch.object(WebSearchTool, "is_available", return_value=False),
        patch.object(PythonTool, "is_available", return_value=False),
    ):
        seed_scovra_agents(db_session)

    personas = _live_seeded_personas(db_session)
    assert set(personas) == set(SEEDED_NAMES)
    for definition in SCOVRA_AGENTS:
        _assert_matches_definition(personas[definition.name], definition)

    state = _load_seed_state()
    for definition in SCOVRA_AGENTS:
        record = state.agents[definition.key]
        assert record.persona_id == personas[definition.name].id
        assert record.definition_hash == definition.definition_hash()
    assert state.default is not None
    assert state.default.definition_hash == SCOVRA_DEFAULT_AGENT.definition_hash()


def test_second_seed_is_a_no_op(db_session: Session) -> None:
    seed_scovra_agents(db_session)
    ids_before = {name: p.id for name, p in _live_seeded_personas(db_session).items()}

    with (
        patch.object(seed_module, "create_seeded_persona") as create_mock,
        patch.object(seed_module, "update_seeded_persona") as update_mock,
        patch.object(
            seed_module, "update_default_assistant_configuration"
        ) as default_mock,
        patch.object(seed_module, "get_kv_store", wraps=get_kv_store) as kv_mock,
    ):
        seed_scovra_agents(db_session)

    create_mock.assert_not_called()
    update_mock.assert_not_called()
    default_mock.assert_not_called()
    # One load, no store.
    assert kv_mock.call_count == 1
    ids_after = {name: p.id for name, p in _live_seeded_personas(db_session).items()}
    assert ids_after == ids_before


def test_admin_edit_survives_reseed_with_unchanged_definitions(
    db_session: Session,
) -> None:
    seed_scovra_agents(db_session)
    scout = _live_seeded_personas(db_session)[SCOUT_AGENT.name]
    scout.description = "Edited by an admin"
    scout.system_prompt = "Admin prompt"
    scout.tools = [tool for tool in scout.tools if tool.in_code_tool_id != "MemoryTool"]
    db_session.commit()

    seed_scovra_agents(db_session)

    scout = _live_seeded_personas(db_session)[SCOUT_AGENT.name]
    assert scout.description == "Edited by an admin"
    assert scout.system_prompt == "Admin prompt"
    assert "MemoryTool" not in _in_code_tool_ids(scout)


def test_changed_definition_is_applied_again(db_session: Session) -> None:
    seed_scovra_agents(db_session)
    scout = _live_seeded_personas(db_session)[SCOUT_AGENT.name]
    scout_id = scout.id
    scout.description = "Edited by an admin"
    scout.display_priority = 99
    db_session.commit()

    changed_scout = SCOUT_AGENT.model_copy(
        update={
            "description": "New code description",
            "starter_messages": [StarterMessage(name="Hi", message="Hi")],
        }
    )
    changed_agents = [
        changed_scout if agent.key == SCOUT_AGENT.key else agent
        for agent in SCOVRA_AGENTS
    ]
    with (
        patch.object(seed_module, "SCOVRA_AGENTS", changed_agents),
        patch.object(seed_module, "create_seeded_persona") as create_mock,
    ):
        seed_scovra_agents(db_session)

    create_mock.assert_not_called()
    scout = _live_seeded_personas(db_session)[SCOUT_AGENT.name]
    assert scout.id == scout_id
    _assert_matches_definition(scout, changed_scout)
    state = _load_seed_state()
    assert state.agents[SCOUT_AGENT.key].definition_hash == (
        changed_scout.definition_hash()
    )


def test_default_agent_gets_house_prompt_and_keeps_tools(
    db_session: Session,
) -> None:
    default_agent = get_default_assistant(db_session)
    assert default_agent is not None
    tool_ids_before = {tool.id for tool in default_agent.tools}

    seed_scovra_agents(db_session)

    db_session.expire_all()
    default_agent = get_default_assistant(db_session)
    assert default_agent is not None
    assert default_agent.system_prompt == DEFAULT_SYSTEM_PROMPT
    assert default_agent.system_prompt.startswith(SCOVRA_HOUSE_PREAMBLE)
    assert "You are an expert assistant" in default_agent.system_prompt
    assert default_agent.starter_messages == SCOVRA_DEFAULT_AGENT.starter_messages
    assert {tool.id for tool in default_agent.tools} == tool_ids_before

    # An admin edit of the default agent survives a re-seed.
    default_agent.system_prompt = "Admin house prompt"
    db_session.commit()
    seed_scovra_agents(db_session)
    db_session.expire_all()
    default_agent = get_default_assistant(db_session)
    assert default_agent is not None
    assert default_agent.system_prompt == "Admin house prompt"


def test_deleted_agent_stays_deleted(db_session: Session) -> None:
    seed_scovra_agents(db_session)
    scout = _live_seeded_personas(db_session)[SCOUT_AGENT.name]
    scout_id = scout.id
    scout.deleted = True
    db_session.commit()

    changed_scout = SCOUT_AGENT.model_copy(update={"description": "Changed"})
    changed_agents = [
        changed_scout if agent.key == SCOUT_AGENT.key else agent
        for agent in SCOVRA_AGENTS
    ]
    seed_scovra_agents(db_session)
    with patch.object(seed_module, "SCOVRA_AGENTS", changed_agents):
        seed_scovra_agents(db_session)

    personas = _live_seeded_personas(db_session)
    assert SCOUT_AGENT.name not in personas
    assert set(personas) == set(SEEDED_NAMES) - {SCOUT_AGENT.name}
    deleted_scout = db_session.get(Persona, scout_id)
    assert deleted_scout is not None
    assert deleted_scout.deleted is True


def test_user_owned_persona_with_the_same_name_is_left_alone(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, f"scovra_seed_{uuid4().hex[:6]}")
    user_scout = Persona(
        user_id=user.id,
        name=SCOUT_AGENT.name,
        description="A user's own agent",
        system_prompt="User prompt",
        task_prompt="",
        is_public=False,
    )
    db_session.add(user_scout)
    db_session.commit()
    try:
        seed_scovra_agents(db_session)

        personas = _live_seeded_personas(db_session)
        assert set(personas) == set(SEEDED_NAMES)
        assert personas[SCOUT_AGENT.name].id != user_scout.id
        db_session.refresh(user_scout)
        assert user_scout.description == "A user's own agent"
        assert user_scout.system_prompt == "User prompt"
    finally:
        db_session.delete(user_scout)
        db_session.commit()
        delete_test_user(db_session, user)


def test_group_owned_persona_with_the_same_name_is_left_alone(
    db_session: Session,
) -> None:
    group = UserGroup(name=f"scovra_seed_{uuid4().hex[:6]}")
    db_session.add(group)
    db_session.flush()
    group_scout = Persona(
        user_id=None,
        owner_group_id=group.id,
        name=SCOUT_AGENT.name,
        description="A group's own agent",
        system_prompt="Group prompt",
        task_prompt="",
        is_public=True,
    )
    db_session.add(group_scout)
    db_session.commit()
    try:
        seed_scovra_agents(db_session)

        personas = _live_seeded_personas(db_session)
        assert personas[SCOUT_AGENT.name].id != group_scout.id
        db_session.refresh(group_scout)
        assert group_scout.description == "A group's own agent"
        assert group_scout.system_prompt == "Group prompt"
        assert group_scout.owner_group_id == group.id
    finally:
        db_session.delete(group_scout)
        db_session.delete(group)
        db_session.commit()


def test_seed_state_pointing_at_the_default_agent_does_not_change_it(
    db_session: Session,
) -> None:
    default_agent = get_default_assistant(db_session)
    assert default_agent is not None
    name_before = default_agent.name
    description_before = default_agent.description
    builtin_id = default_agent.id
    get_kv_store().store(
        SCOVRA_SEED_STATE_KEY,
        ScovraSeedState(
            agents={
                SCOUT_AGENT.key: AgentSeedRecord(
                    persona_id=builtin_id, definition_hash="stale"
                )
            },
            default=None,
        ).to_json(),
    )

    seed_scovra_agents(db_session)

    db_session.expire_all()
    default_agent = get_default_assistant(db_session)
    assert default_agent is not None
    assert default_agent.id == builtin_id
    assert default_agent.name == name_before
    assert default_agent.description == description_before
    assert default_agent.builtin_persona is True


def test_seed_failure_does_not_raise(db_session: Session) -> None:
    with (
        patch.object(
            seed_module,
            "get_tools_by_in_code_tool_ids",
            side_effect=RuntimeError("database is unhappy"),
        ),
        patch.object(seed_module.logger, "exception") as log_exception,
    ):
        seed_scovra_agents(db_session)

    log_exception.assert_called_once()
    assert _live_seeded_personas(db_session) == {}


def test_one_agent_failure_does_not_stop_the_others(db_session: Session) -> None:
    real_create = seed_module.create_seeded_persona

    def _create_or_fail(
        session: Session, fields: SeededPersonaFields, tools: Sequence[Tool]
    ) -> Persona:
        if fields.name == SCOUT_AGENT.name:
            raise RuntimeError("Scout cannot be created")
        return real_create(session, fields, tools)

    create_mock = MagicMock(side_effect=_create_or_fail)
    with patch.object(seed_module, "create_seeded_persona", create_mock):
        seed_scovra_agents(db_session)

    personas = _live_seeded_personas(db_session)
    assert set(personas) == set(SEEDED_NAMES) - {SCOUT_AGENT.name}
    state = _load_seed_state()
    assert SCOUT_AGENT.key not in state.agents

    # The next start creates the missing agent.
    seed_scovra_agents(db_session)
    assert set(_live_seeded_personas(db_session)) == set(SEEDED_NAMES)


def test_multi_tenant_skips_the_seed(db_session: Session) -> None:
    with patch.object(seed_module, "MULTI_TENANT", True):
        seed_scovra_agents(db_session)

    assert _live_seeded_personas(db_session) == {}
    with pytest.raises(KvKeyNotFoundError):
        get_kv_store().load(SCOVRA_SEED_STATE_KEY, refresh_cache=True)
