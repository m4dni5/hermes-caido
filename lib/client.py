"""Caido GraphQL client — raw HTTP, no SDK dependency.

Reads CAIDO_PAT and CAIDO_URL from env or ~/.hermes/.env or
~/.claude/config/secrets.json.  Uses aiohttp for async HTTP.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_HERMES_ENV = Path.home() / ".hermes" / ".env"
_CLAUDE_SECRETS = Path.home() / ".claude" / "config" / "secrets.json"

_session: aiohttp.ClientSession | None = None
_url: str | None = None
_pat: str | None = None


def _load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            env[key] = value
    return env


def _resolve_credentials() -> tuple[str, str]:
    pat = os.environ.get("CAIDO_PAT")
    url = os.environ.get("CAIDO_URL")
    if pat and url:
        return pat, url

    dotenv = _load_dotenv(_HERMES_ENV)
    pat = pat or dotenv.get("CAIDO_PAT")
    url = url or dotenv.get("CAIDO_URL")

    if (not pat or not url) and _CLAUDE_SECRETS.is_file():
        try:
            secrets = json.loads(_CLAUDE_SECRETS.read_text())
            caido = secrets.get("caido", {})
            pat = pat or caido.get("pat")
            url = url or caido.get("url")
        except Exception:
            pass

    missing: list[str] = []
    if not pat:
        missing.append("CAIDO_PAT")
    if not url:
        missing.append("CAIDO_URL")
    if missing:
        raise RuntimeError(
            f"Missing credential(s): {', '.join(missing)}. "
            f"Set as env vars or in {_HERMES_ENV}."
        )
    return pat, url  # type: ignore[return-value]


async def _get_session() -> tuple[aiohttp.ClientSession, str]:
    global _session, _url, _pat
    if _session and not _session.closed:
        return _session, _url  # type: ignore[return-value]

    _pat, _url = _resolve_credentials()
    _session = aiohttp.ClientSession(
        headers={
            "Authorization": f"Bearer {_pat}",
            "Content-Type": "application/json",
        },
    )
    return _session, _url  # type: ignore[return-value]


async def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query/mutation against the Caido API."""
    session, url = await _get_session()
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    async with session.post(f"{url}/graphql", json=payload) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"GraphQL HTTP {resp.status}: {text[:500]}")
        data = await resp.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data.get("data", {})


async def health() -> dict[str, Any]:
    """Check Caido health via GraphQL."""
    try:
        data = await graphql("query { health { status version } }")
        return data.get("health", {})
    except Exception:
        # Fallback: try REST
        session, url = await _get_session()
        async with session.get(f"{url}/") as resp:
            return {"status": "ok" if resp.status == 200 else "error", "statusCode": resp.status}


async def close() -> None:
    """Close the shared session."""
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None
