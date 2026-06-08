"""Caido GraphQL client — raw HTTP, no SDK dependency.

Authentication uses the OAuth2 device code flow via caido.io, matching
the Caido SDK's PATApprover pattern.  Caches access/refresh tokens at
~/.config/caido-py/secrets.json for reuse across sessions.

Credential resolution order:
  1. Environment variables (CAIDO_PAT, CAIDO_URL)
  2. ~/.hermes/.env
  3. ~/.claude/config/secrets.json (caido key — shared with TS CLI)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)

# ── paths ──────────────────────────────────────────────────────────────

_HERMES_ENV = Path.home() / ".hermes" / ".env"
_CLAUDE_SECRETS = Path.home() / ".claude" / "config" / "secrets.json"
_TOKEN_CACHE = Path.home() / ".config" / "caido-py" / "secrets.json"
_CLOUD_API = "https://api.caido.io"

# ── singleton state ────────────────────────────────────────────────────

_session: aiohttp.ClientSession | None = None
_url: str | None = None
_access_token: str | None = None
_refresh_token: str | None = None
_expires_at: datetime | None = None


# ── credential resolution ──────────────────────────────────────────────

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
    """Return (pat, url) from env/secrets. Raises RuntimeError if missing."""
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


# ── token cache ────────────────────────────────────────────────────────

def _load_cached_token() -> bool:
    """Load cached access/refresh token. Returns True if valid and not expired."""
    global _access_token, _refresh_token, _expires_at

    if not _TOKEN_CACHE.is_file():
        return False

    try:
        data = json.loads(_TOKEN_CACHE.read_text())
        _access_token = data.get("accessToken")
        _refresh_token = data.get("refreshToken")
        expires_str = data.get("expiresAt")
        if expires_str:
            _expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        return _access_token is not None and (
            _expires_at is None or _expires_at > datetime.now(timezone.utc)
        )
    except Exception:
        return False


def _save_cached_token() -> None:
    """Persist access/refresh token to cache."""
    _TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if _access_token:
        data["accessToken"] = _access_token
    if _refresh_token:
        data["refreshToken"] = _refresh_token
    if _expires_at:
        data["expiresAt"] = _expires_at.isoformat()
    _TOKEN_CACHE.write_text(json.dumps(data, indent=2))


def _load_claude_cached_token() -> bool:
    """Try loading cached token from ~/.claude/config/secrets.json (TS CLI cache)."""
    global _access_token, _refresh_token, _expires_at

    if not _CLAUDE_SECRETS.is_file():
        return False

    try:
        data = json.loads(_CLAUDE_SECRETS.read_text())
        caido = data.get("caido", {})
        cached = caido.get("cachedToken", {})
        _access_token = cached.get("accessToken")
        _refresh_token = cached.get("refreshToken")
        expires_str = cached.get("expiresAt")
        if expires_str:
            _expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        if _access_token and (_expires_at is None or _expires_at > datetime.now(timezone.utc)):
            _save_cached_token()  # copy to our own cache
            return True
    except Exception:
        pass
    return False


# ── OAuth2 device code flow ────────────────────────────────────────────

async def _exchange_pat_for_token(pat: str, session: aiohttp.ClientSession) -> bool:
    """Exchange PAT for access token via caido.io OAuth2 device flow.

    This replicates the Caido SDK's PATApprover pattern:
    1. Start device code flow against the Caido instance
    2. Auto-approve using the PAT via caido.io
    3. Poll for the access token
    """
    global _access_token, _refresh_token, _expires_at

    # Step 1: Start device code flow on the Caido instance
    async with session.post(
        f"{_url}/oauth2/device/code",
        json={"client_id": "caido-sdk", "scope": "read write"},
    ) as resp:
        if resp.status != 200:
            logger.error("Device code flow failed to start: %d", resp.status)
            return False
        device_data = await resp.json()

    user_code = device_data.get("user_code")
    device_code = device_data.get("device_code")
    interval = device_data.get("interval", 5)

    if not user_code or not device_code:
        logger.error("Missing user_code or device_code in response")
        return False

    # Step 2: Auto-approve via caido.io using PAT
    approve_url = f"{_CLOUD_API}/oauth2/device/approve"
    query = urlencode({"user_code": user_code, "scope": "read,write"})
    async with session.post(
        f"{approve_url}?{query}",
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    ) as resp:
        if resp.status < 200 or resp.status >= 300:
            logger.error("PAT approval failed: %d %s", resp.status, await resp.text())
            return False

    # Step 3: Poll for token
    token_url = f"{_url}/oauth2/token"
    for _ in range(30):  # max 30 polls
        import asyncio
        await asyncio.sleep(interval)
        async with session.post(
            token_url,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": "caido-sdk",
            },
        ) as resp:
            if resp.status == 200:
                token_data = await resp.json()
                _access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in")
                if expires_in:
                    from datetime import timedelta
                    _expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                _save_cached_token()
                return True
            body = await resp.json()
            if body.get("error") == "authorization_pending":
                continue
            logger.error("Token poll error: %s", body)
            return False

    logger.error("Token poll timed out")
    return False


async def _refresh_access_token(session: aiohttp.ClientSession) -> bool:
    """Refresh the access token using the refresh token."""
    global _access_token, _refresh_token, _expires_at

    if not _refresh_token:
        return False

    token_url = f"{_url}/oauth2/token"
    async with session.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": _refresh_token,
            "client_id": "caido-sdk",
        },
    ) as resp:
        if resp.status != 200:
            return False
        token_data = await resp.json()
        _access_token = token_data.get("access_token")
        _refresh_token = token_data.get("refresh_token") or _refresh_token
        expires_in = token_data.get("expires_in")
        if expires_in:
            from datetime import timedelta
            _expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        _save_cached_token()
        return True


# ── session management ─────────────────────────────────────────────────

async def _get_session() -> tuple[aiohttp.ClientSession, str]:
    global _session, _url, _access_token

    if _session and not _session.closed and _access_token:
        return _session, _url  # type: ignore[return-value]

    pat, _url = _resolve_credentials()

    # Try loading cached token (our cache first, then TS CLI's cache)
    has_token = _load_cached_token() or _load_claude_cached_token()

    if not has_token:
        # Need to do the full device code flow
        _session = aiohttp.ClientSession()
        success = await _exchange_pat_for_token(pat, _session)
        if not success:
            await _session.close()
            raise RuntimeError("Failed to authenticate with Caido")

    # Check if token is expired, try refresh
    if _expires_at and _expires_at <= datetime.now(timezone.utc):
        if _session is None:
            _session = aiohttp.ClientSession()
        if not await _refresh_access_token(_session):
            # Refresh failed, re-authenticate
            success = await _exchange_pat_for_token(pat, _session)
            if not success:
                raise RuntimeError("Failed to re-authenticate with Caido")

    if _session is None:
        _session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {_access_token}",
                "Content-Type": "application/json",
            },
        )
    else:
        _session.headers.update({
            "Authorization": f"Bearer {_access_token}",
            "Content-Type": "application/json",
        })

    return _session, _url  # type: ignore[return-value]


# ── API calls ──────────────────────────────────────────────────────────

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
