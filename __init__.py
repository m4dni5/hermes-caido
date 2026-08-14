"""Hermes Agent Caido plugin — registration.

Registers tools for interacting with the Caido HTTP proxy:
onboard, search, recent, get, findings, create_finding, delete_finding,
health, auth_setup, export_curl, replay, automate, automate_status.

Design (tool-search era): every operation an agent-operator performs is a
registered tool. Tool descriptions carry the decisions; one recipe skill
(caido:caido) holds the agent-operator cookbook — shared-workspace guidance,
tool map, replay/automate decisions, pitfalls. Advanced config (scopes,
filters, envs, projects, raw session CRUD) stays in the lib/ layer, callable
via execute_code.

No external SDK dependency — uses raw GraphQL via aiohttp.
"""

from __future__ import annotations

import logging
from pathlib import Path

# schemas is flat (no package-relative imports), so importing it at module
# level works both under the framework loader (hermes_plugins.caido) and
# when pytest imports this __init__.py as a bare module. caido_tools has
# package-relative lib imports, so it's imported lazily inside register()
# where the loader always provides the correct package context.
#
# The try/except covers the two load contexts: relative under the framework
# loader (namespaced package, __package__ set), absolute fallback when
# pytest imports this file as a bare module (project dir has a hyphen, so
# it can't be a real package parent).
try:
    from . import schemas
except ImportError:
    import sys  # noqa: PLC0415

    sys.path.insert(0, str(Path(__file__).parent))
    import schemas  # noqa: PLC0415

logger = logging.getLogger(__name__)


def register(ctx) -> None:  # noqa: ANN001 — plugin context type
    """Register Caido tools with the Hermes tool registry."""
    from . import caido_tools as tools

    # Expose plugin path for skills and auth helper — works under any profile
    import os

    plugin_path = ctx.manifest.path or str(Path(__file__).parent)
    os.environ["CAIDO_PLUGIN_DIR"] = plugin_path

    _tools = [
        # Orientation & health
        ("caido_onboard",        schemas.CAIDO_ONBOARD,        tools.handle_onboard,        "Connect and gather full Caido context"),
        ("caido_health",         schemas.CAIDO_HEALTH,         tools.handle_health,         "Check Caido health"),
        # Proxy history
        ("caido_search",         schemas.CAIDO_SEARCH,         tools.handle_search,         "Search proxy history with HTTPQL"),
        ("caido_recent",         schemas.CAIDO_RECENT,         tools.handle_recent,         "Get recent intercepted requests"),
        ("caido_get",            schemas.CAIDO_GET,            tools.handle_get,            "Get request/response by ID (Request.id or UI number)"),
        # Findings
        ("caido_findings",       schemas.CAIDO_FINDINGS,       tools.handle_findings,       "List security findings"),
        ("caido_create_finding", schemas.CAIDO_CREATE_FINDING, tools.handle_create_finding, "Create a security finding"),
        ("caido_delete_finding", schemas.CAIDO_DELETE_FINDING, tools.handle_delete_finding, "Delete a security finding"),
        # Operations
        ("caido_replay",         schemas.CAIDO_REPLAY,         tools.handle_replay,         "Replay a request, optionally edited"),
        ("caido_automate",       schemas.CAIDO_AUTOMATE,       tools.handle_automate,       "Run an automate campaign"),
        ("caido_automate_status", schemas.CAIDO_AUTOMATE_STATUS, tools.handle_automate_status, "Poll automate task status"),
        ("caido_export_curl",    schemas.CAIDO_EXPORT_CURL,    tools.handle_export_curl,    "Export request as curl command"),
        ("caido_auth_setup",     schemas.CAIDO_AUTH_SETUP,     tools.handle_auth_setup,     "Run device-code auth flow"),
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

    # Bundle skills — one agent-operator cookbook
    skills_dir = Path(__file__).parent / "skills"
    for skill_name in ("caido",):
        skill_path = skills_dir / skill_name / "SKILL.md"
        if skill_path.exists():
            ctx.register_skill(skill_name, skill_path)
            logger.debug("Registered skill: caido:%s", skill_name)
        else:
            logger.warning("Skill file not found: %s", skill_path)

    logger.info("Caido plugin loaded — %d tools, 1 skill", len(_tools))
