"""Hermes Agent Caido plugin — registration.

Registers 15 tools for interacting with the Caido HTTP proxy:
search, replay, sessions, collections, findings, scopes, filters,
environments, projects, and health.
"""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_SDK_PACKAGE = "caido-sdk-client"


def _ensure_sdk() -> bool:
    """Install caido-sdk-client if missing. Returns True if available."""
    try:
        importlib.import_module("caido_sdk_client")
        return True
    except ImportError:
        pass

    logger.info("Caido plugin: installing %s ...", _SDK_PACKAGE)
    try:
        # Ensure pip is available in the venv (stdlib, always present)
        subprocess.check_call(
            [sys.executable, "-m", "ensurepip", "--upgrade", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("Caido plugin: ensurepip failed: %s", exc)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", _SDK_PACKAGE, "--quiet"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(
                "Caido plugin: pip install failed (rc=%d)\nstdout: %s\nstderr: %s",
                result.returncode, result.stdout, result.stderr,
            )
            return False
        importlib.import_module("caido_sdk_client")
        logger.info("Caido plugin: %s installed successfully", _SDK_PACKAGE)
        return True
    except Exception as exc:
        logger.error("Caido plugin: failed to install %s: %s", _SDK_PACKAGE, exc)
        return False


# Import tool modules only after SDK is available
def _load_tools():  # noqa: ANN202
    from . import schemas, tools
    return schemas, tools



def register(ctx) -> None:  # noqa: ANN001 — plugin context type
    """Register all Caido tools with the Hermes tool registry."""
    if not _ensure_sdk():
        logger.error("Caido plugin: SDK not available, skipping registration")
        return

    schemas, tools = _load_tools()

    _tools = [
        ("caido_search",         schemas.CAIDO_SEARCH,         tools.handle_search,         "Search proxy history with HTTPQL"),
        ("caido_recent",         schemas.CAIDO_RECENT,         tools.handle_recent,         "Get recent intercepted requests"),
        ("caido_get",            schemas.CAIDO_GET,            tools.handle_get,            "Get request/response by ID"),
        ("caido_replay",         schemas.CAIDO_REPLAY,         tools.handle_replay,         "Replay a request through the proxy"),
        ("caido_send_raw",       schemas.CAIDO_SEND_RAW,       tools.handle_send_raw,       "Send a raw HTTP request"),
        ("caido_sessions",       schemas.CAIDO_SESSIONS,       tools.handle_sessions,       "List replay sessions"),
        ("caido_create_session", schemas.CAIDO_CREATE_SESSION, tools.handle_create_session, "Create a replay session"),
        ("caido_collections",    schemas.CAIDO_COLLECTIONS,    tools.handle_collections,    "List replay collections"),
        ("caido_findings",       schemas.CAIDO_FINDINGS,       tools.handle_findings,       "List security findings"),
        ("caido_create_finding", schemas.CAIDO_CREATE_FINDING, tools.handle_create_finding, "Create a security finding"),
        ("caido_scopes",         schemas.CAIDO_SCOPES,         tools.handle_scopes,         "List scopes"),
        ("caido_filters",        schemas.CAIDO_FILTERS,        tools.handle_filters,        "List filter presets"),
        ("caido_envs",           schemas.CAIDO_ENVS,           tools.handle_envs,           "List environments"),
        ("caido_projects",       schemas.CAIDO_PROJECTS,       tools.handle_projects,       "List projects"),
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

    logger.info("Caido plugin loaded — %d tools registered", len(_tools))
