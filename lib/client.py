"""Authentication and Caido client singleton.

Reads ``CAIDO_PAT`` and ``CAIDO_URL`` from the environment (or
``~/.hermes/.env`` as fallback) and exposes lazy helpers that return a
shared, pre-connected SDK ``Client`` and ``GraphQLClient``.
"""

from __future__ import annotations

import os
from pathlib import Path

from caido_sdk_client.auth.types import AuthCacheFile, PATAuthOptions
from caido_sdk_client.client import Client
from caido_sdk_client.graphql import GraphQLClient

# ── paths ────────────────────────────────────────────────────────────────────

_HERMES_ENV = Path.home() / ".hermes" / ".env"
_CLAUDE_SECRETS = Path.home() / ".claude" / "config" / "secrets.json"
_CACHE_FILE = Path.home() / ".config" / "caido-py" / "secrets.json"

# ── singleton state ──────────────────────────────────────────────────────────

_client: Client | None = None


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines from a dotenv file, ignoring comments."""
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
    """Return ``(pat, url)`` from env vars or ``~/.hermes/.env``.

    Raises ``RuntimeError`` with a clear message if either value is missing.
    """
    pat = os.environ.get("CAIDO_PAT")
    url = os.environ.get("CAIDO_URL")

    if pat and url:
        return pat, url

    # Fallback: try ~/.hermes/.env
    dotenv = _load_dotenv(_HERMES_ENV)
    pat = pat or dotenv.get("CAIDO_PAT")
    url = url or dotenv.get("CAIDO_URL")

    # Fallback: try ~/.claude/config/secrets.json (caido key)
    if (not pat or not url) and _CLAUDE_SECRETS.is_file():
        try:
            import json as _json
            secrets = _json.loads(_CLAUDE_SECRETS.read_text())
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
            f"Missing required credential(s): {', '.join(missing)}. "
            f"Set them as environment variables or in {_HERMES_ENV}."
        )
    return pat, url  # type: ignore[return-value]


async def get_client() -> Client:
    """Return the singleton ``Client``, creating and connecting it on first call."""
    global _client
    if _client is not None:
        return _client

    pat, url = _resolve_credentials()

    # Ensure cache directory exists
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    auth = PATAuthOptions(
        pat=pat,
        cache=AuthCacheFile(file=str(_CACHE_FILE)),
    )

    _client = Client(url, auth=auth)
    await _client.connect()
    return _client


async def get_graphql() -> GraphQLClient:
    """Return the ``GraphQLClient`` from the shared ``Client``."""
    client = await get_client()
    return client.graphql
