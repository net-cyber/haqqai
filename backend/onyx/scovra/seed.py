"""Seed the Scovra agents and the default agent configuration on api_server start.

Each definition in `onyx.scovra.agents` has a hash. The seed keeps the hash that it
last applied in the KV store, and it writes a definition again only when its hash
changes. Admin edits therefore stay after a restart until the code definition
changes. The seed does not create again an agent that an admin deleted.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from onyx.db.models import Tool
from onyx.db.persona import update_default_assistant_configuration
from onyx.db.scovra import (
    SeededPersonaFields,
    create_seeded_persona,
    get_seedable_persona_by_name,
    get_seeded_persona_by_id,
    get_tools_by_in_code_tool_ids,
    set_default_assistant_starter_messages__no_commit,
    update_seeded_persona,
)
from onyx.key_value_store.factory import get_kv_store
from onyx.key_value_store.interface import KvKeyNotFoundError
from onyx.scovra.agents import (
    SCOVRA_AGENTS,
    SCOVRA_DEFAULT_AGENT,
    ScovraAgentDefinition,
)
from onyx.utils.logger import setup_logger
from onyx.utils.special_types import JSON_ro
from shared_configs.configs import MULTI_TENANT

logger = setup_logger()

SCOVRA_SEED_STATE_KEY = "scovra_agent_seed_state"
# Key of the default agent record in the seed state. Agent keys must differ from it.
DEFAULT_AGENT_STATE_KEY: str = "default"


class AgentSeedRecord(BaseModel):
    persona_id: int
    definition_hash: str


class DefaultAgentSeedRecord(BaseModel):
    definition_hash: str


class ScovraSeedState(BaseModel):
    """Stored as {agent_key: {"persona_id", "definition_hash"}, "default": {"definition_hash"}}."""

    agents: dict[str, AgentSeedRecord]
    default: DefaultAgentSeedRecord | None

    @classmethod
    def from_json(cls, raw: JSON_ro) -> "ScovraSeedState":
        agents: dict[str, AgentSeedRecord] = {}
        default: DefaultAgentSeedRecord | None = None
        if not isinstance(raw, Mapping):
            logger.warning("Ignoring Scovra seed state with an unexpected shape")
            return cls(agents=agents, default=default)
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            try:
                if key == DEFAULT_AGENT_STATE_KEY:
                    default = DefaultAgentSeedRecord.model_validate(value)
                else:
                    agents[key] = AgentSeedRecord.model_validate(value)
            except ValidationError:
                logger.warning("Ignoring an invalid Scovra seed state entry: %s", key)
        return cls(agents=agents, default=default)

    def to_json(self) -> dict[str, JSON_ro]:
        data: dict[str, JSON_ro] = {
            key: record.model_dump() for key, record in self.agents.items()
        }
        if self.default is not None:
            data[DEFAULT_AGENT_STATE_KEY] = self.default.model_dump()
        return data


def _load_seed_state() -> ScovraSeedState:
    try:
        # Read Postgres, not the cache: the cache can keep an old value for a day.
        raw = get_kv_store().load(SCOVRA_SEED_STATE_KEY, refresh_cache=True)
    except KvKeyNotFoundError:
        return ScovraSeedState(agents={}, default=None)
    return ScovraSeedState.from_json(raw)


def _seed_agent(
    db_session: Session,
    definition: ScovraAgentDefinition,
    record: AgentSeedRecord | None,
    tools_by_in_code_id: Mapping[str, Tool],
) -> AgentSeedRecord:
    definition_hash = definition.definition_hash()

    if record is not None:
        persona = get_seeded_persona_by_id(db_session, record.persona_id)
        if persona is None or persona.deleted:
            logger.notice(
                "Scovra agent '%s' (persona %s) was deleted. The seed does not create it again.",
                definition.key,
                record.persona_id,
            )
            return record
    else:
        persona = get_seedable_persona_by_name(db_session, definition.name)

    fields = SeededPersonaFields(
        name=definition.name,
        description=definition.description,
        system_prompt=definition.system_prompt,
        task_prompt=definition.task_prompt,
        starter_messages=definition.starter_messages,
        icon_name=definition.icon_name,
        display_priority=definition.display_priority,
    )
    tools = [
        tools_by_in_code_id[in_code_tool_id]
        for in_code_tool_id in definition.in_code_tool_ids
        if in_code_tool_id in tools_by_in_code_id
    ]

    if persona is None:
        persona = create_seeded_persona(db_session, fields, tools)
        logger.notice(
            "Created Scovra agent '%s' (persona %s)", definition.key, persona.id
        )
    elif record is None or record.definition_hash != definition_hash:
        update_seeded_persona(db_session, persona, fields, tools)
        logger.notice(
            "Updated Scovra agent '%s' (persona %s)", definition.key, persona.id
        )

    return AgentSeedRecord(persona_id=persona.id, definition_hash=definition_hash)


def _seed_default_agent(
    db_session: Session, record: DefaultAgentSeedRecord | None
) -> DefaultAgentSeedRecord:
    definition_hash = SCOVRA_DEFAULT_AGENT.definition_hash()
    if record is not None and record.definition_hash == definition_hash:
        return record

    set_default_assistant_starter_messages__no_commit(
        db_session, SCOVRA_DEFAULT_AGENT.starter_messages
    )
    # Commits the starter messages too. tool_ids=None keeps the admin's tools.
    update_default_assistant_configuration(
        db_session=db_session,
        system_prompt=SCOVRA_DEFAULT_AGENT.system_prompt,
        update_system_prompt=True,
    )
    logger.notice("Applied the Scovra configuration to the default agent")
    return DefaultAgentSeedRecord(definition_hash=definition_hash)


def _seed(db_session: Session) -> None:
    state = _load_seed_state()

    in_code_tool_ids = sorted(
        {tool_id for agent in SCOVRA_AGENTS for tool_id in agent.in_code_tool_ids}
    )
    tools_by_in_code_id = get_tools_by_in_code_tool_ids(db_session, in_code_tool_ids)
    for missing_tool_id in sorted(set(in_code_tool_ids) - set(tools_by_in_code_id)):
        logger.warning(
            "Scovra seed: no tool row for '%s'. Agents get the other tools.",
            missing_tool_id,
        )

    agents = dict(state.agents)
    for definition in SCOVRA_AGENTS:
        try:
            agents[definition.key] = _seed_agent(
                db_session,
                definition,
                state.agents.get(definition.key),
                tools_by_in_code_id,
            )
        except Exception:
            db_session.rollback()
            logger.exception("Failed to seed Scovra agent '%s'", definition.key)

    default = state.default
    try:
        default = _seed_default_agent(db_session, state.default)
    except Exception:
        db_session.rollback()
        logger.exception("Failed to apply the Scovra default agent configuration")

    new_state = ScovraSeedState(agents=agents, default=default)
    if new_state != state:
        get_kv_store().store(SCOVRA_SEED_STATE_KEY, new_state.to_json())


def seed_scovra_agents(db_session: Session) -> None:
    """Create or update the Scovra agents and the default agent. This never raises,
    so a seed failure cannot stop the api_server from starting."""
    if MULTI_TENANT:
        logger.notice("Skipping the Scovra agent seed: MULTI_TENANT is set")
        return
    try:
        _seed(db_session)
    except Exception:
        logger.exception("Scovra agent seed failed. Startup continues.")
        try:
            db_session.rollback()
        except Exception:
            logger.exception("Rollback after the Scovra agent seed failure failed")
