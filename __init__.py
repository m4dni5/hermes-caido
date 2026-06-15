"""Hermes Agent Caido plugin — registration.

Registers hot-path tools for interacting with the Caido HTTP proxy:
onboard, search, recent, get, findings, create_finding, health.

All other operations (replay, session management, findings CRUD,
export curl, scopes, filters, envs, projects, auth setup) are accessed via
bundled skills:
  - caido:replay  — session management, edit-and-replay
  - caido:utils   — auth setup, findings, export curl, scopes, filters, envs, projects
  - caido:automate — session CRUD, placeholders, payloads, task control

No external SDK dependency — uses raw GraphQL via aiohttp.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import schemas, caido_tools as tools

logger = logging.getLogger(__name__)


def register(ctx) -> None:  # noqa: ANN001 — plugin context type
    """Register hot-path Caido tools with the Hermes tool registry."""
    _tools = [
        # Hot path — always available, schema-guided
        ("caido_onboard",        schemas.CAIDO_ONBOARD,        tools.handle_onboard,        "Connect and gather full Caido context"),
        ("caido_search",         schemas.CAIDO_SEARCH,         tools.handle_search,         "Search proxy history with HTTPQL"),
        ("caido_recent",         schemas.CAIDO_RECENT,         tools.handle_recent,         "Get recent intercepted requests"),
        ("caido_get",            schemas.CAIDO_GET,            tools.handle_get,            "Get request/response by ID"),
        ("caido_findings",       schemas.CAIDO_FINDINGS,       tools.handle_findings,       "List security findings"),
        ("caido_create_finding", schemas.CAIDO_CREATE_FINDING, tools.handle_create_finding, "Create a security finding"),
        ("caido_health",         schemas.CAIDO_HEALTH,         tools.handle_health,         "Check Caido health"),
    ]

    for name, schema, handler, description in _tools:
        ctx.register_tool(
            name=name,
            toolset="caido",
            schema=schema,
            handler=handler,
            description=description,
            is_async=True,
        )
        logger.debug("Registered tool: %s", name)

    # Bundle skills
    skills_dir = Path(__file__).parent / "skills"
    for skill_name in ("replay", "utils", "automate"):
        skill_path = skills_dir / skill_name / "SKILL.md"
        if skill_path.exists():
            ctx.register_skill(skill_name, skill_path)
            logger.debug("Registered skill: caido:%s", skill_name)
        else:
            logger.warning("Skill file not found: %s", skill_path)

    logger.info("Caido plugin loaded — %d tools, 3 skills", len(_tools))
