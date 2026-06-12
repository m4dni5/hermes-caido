"""Caido GraphQL client — raw HTTP, no SDK dependency.

Authentication replicates the Caido SDK's OAuth2 device code flow:
1. startAuthenticationFlow mutation → user_code + request_id
2. PATApprover: approve via caido.io cloud API using PAT
3. createdAuthenticationToken subscription (websocket) → access token
4. refreshAuthenticationToken mutation → token refresh

Token cache at ~/.config/caido-py/secrets.json.
Reads PAT from env/secrets (same resolution as before).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)

# ── paths ──────────────────────────────────────────────────────────────

_HERMES_ENV = Path.home() / ".hermes" / ".env"
_HERMES_CACHE = Path.home() / ".hermes" / "cache" / "caido-token.json"
_CLAUDE_SECRETS = Path.home() / ".claude" / "config" / "secrets.json"
_CLOUD_API = "https://api.caido.io"

# ── singleton state ────────────────────────────────────────────────────

_session: aiohttp.ClientSession | None = None
_ws_session: aiohttp.ClientSession | None = None
_url: str | None = None
_access_token: str | None = None
_refresh_token: str | None = None
_expires_at: datetime | None = None
_current_loop: object | None = None  # Track which event loop owns _session

# ── GraphQL documents ─────────────────────────────────────────────────

START_AUTH_FLOW = """
mutation StartAuthenticationFlow {
    startAuthenticationFlow {
        request { id userCode verificationUrl expiresAt }
        error { ... on AuthenticationUserError { code reason }
                ... on CloudUserError { code reason }
                ... on InternalUserError { code message }
                ... on OtherUserError { code } }
    }
}
"""

REFRESH_TOKEN = """
mutation RefreshAuthenticationToken($refreshToken: Token!) {
    refreshAuthenticationToken(refreshToken: $refreshToken) {
        token { accessToken expiresAt refreshToken scopes }
        error { ... on AuthenticationUserError { code reason }
                ... on CloudUserError { code reason }
                ... on InternalUserError { code message }
                ... on OtherUserError { code } }
    }
}
"""

CREATED_TOKEN_SUB = """
subscription CreatedAuthenticationToken($requestId: ID!) {
    createdAuthenticationToken(requestId: $requestId) {
        token { accessToken expiresAt refreshToken scopes }
        error { ... on AuthenticationUserError { code reason }
                ... on InternalUserError { code message }
                ... on OtherUserError { code } }
    }
}
"""


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


def _resolve_pat() -> str:
    """Return PAT from env/secrets. Raises RuntimeError if missing."""
    pat = os.environ.get("CAIDO_PAT")
    if pat:
        return pat

    dotenv = _load_dotenv(_HERMES_ENV)
    pat = pat or dotenv.get("CAIDO_PAT")

    if not pat and _CLAUDE_SECRETS.is_file():
        try:
            secrets = json.loads(_CLAUDE_SECRETS.read_text())
            pat = pat or secrets.get("caido", {}).get("pat")
        except Exception:
            pass

    if not pat:
        raise RuntimeError(f"Missing CAIDO_PAT. Set as env var or in {_HERMES_ENV}.")
    return pat


def _resolve_url() -> str:
    """Return Caido instance URL from env/secrets."""
    url = os.environ.get("CAIDO_URL")
    if url:
        return url

    dotenv = _load_dotenv(_HERMES_ENV)
    url = url or dotenv.get("CAIDO_URL")

    if not url and _CLAUDE_SECRETS.is_file():
        try:
            secrets = json.loads(_CLAUDE_SECRETS.read_text())
            url = url or secrets.get("caido", {}).get("url")
        except Exception:
            pass

    if not url:
        raise RuntimeError(f"Missing CAIDO_URL. Set as env var or in {_HERMES_ENV}.")
    return url


# ── token cache ────────────────────────────────────────────────────────

def _load_cached_token() -> bool:
    """Load cached token. Returns True if valid and not expired."""
    global _access_token, _refresh_token, _expires_at

    for cache_path in [_HERMES_CACHE, _CLAUDE_SECRETS]:
        if not cache_path.is_file():
            continue
        try:
            data = json.loads(cache_path.read_text())
            if cache_path == _CLAUDE_SECRETS:
                data = data.get("caido", {}).get("cachedToken", {})

            _access_token = data.get("accessToken") or data.get("access_token")
            _refresh_token = data.get("refreshToken") or data.get("refresh_token")
            expires_str = data.get("expiresAt") or data.get("expires_at")
            if expires_str:
                _expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))

            if _access_token and (_expires_at is None or _expires_at > datetime.now(timezone.utc)):
                if cache_path == _CLAUDE_SECRETS:
                    _save_cached_token()  # copy to our cache
                return True
        except Exception:
            continue
    return False


def _save_cached_token() -> None:
    """Persist token to cache."""
    _HERMES_CACHE.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if _access_token:
        data["accessToken"] = _access_token
    if _refresh_token:
        data["refreshToken"] = _refresh_token
    if _expires_at:
        data["expiresAt"] = _expires_at.isoformat()
    _HERMES_CACHE.write_text(json.dumps(data, indent=2))


# ── OAuth2 device code flow (via GraphQL + websocket) ─────────────────

async def _gql_raw(url: str, query: str, variables: dict | None = None) -> dict[str, Any]:
    """Execute a raw GraphQL request (no auth header)."""
    async with aiohttp.ClientSession() as s:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        async with s.post(f"{url}/graphql", json=payload) as resp:
            data = await resp.json()
            if "errors" in data:
                raise RuntimeError(f"GraphQL errors: {data['errors']}")
            return data.get("data", {})


async def _get_device_information(pat: str, user_code: str) -> list[str]:
    """Fetch available scopes for a device code from caido.io."""
    info_url = f"{_CLOUD_API}/oauth2/device/information"
    params = urlencode({"user_code": user_code})
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{info_url}?{params}",
            headers={
                "Authorization": f"Bearer {pat}",
                "Accept": "application/json",
            },
        ) as resp:
            if resp.status < 200 or resp.status >= 300:
                body = await resp.text()
                raise RuntimeError(f"Device info failed ({resp.status}): {body[:300]}")
            data = await resp.json()
            scopes = [scope["name"] for scope in data.get("scopes", [])]
            if not scopes:
                raise RuntimeError(f"No scopes returned from device info: {data}")
            return scopes


async def _approve_via_cloud(pat: str, user_code: str) -> None:
    """Approve device code via caido.io using PAT."""
    # Step 1: Get available scopes from device information
    scopes = await _get_device_information(pat, user_code)
    logger.info("Caido auth: approving scopes %s", scopes)

    # Step 2: Approve with the fetched scopes
    approve_url = f"{_CLOUD_API}/oauth2/device/approve"
    params = urlencode({"user_code": user_code, "scope": ",".join(scopes)})
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{approve_url}?{params}",
            headers={
                "Authorization": f"Bearer {pat}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        ) as resp:
            if resp.status < 200 or resp.status >= 300:
                body = await resp.text()
                raise RuntimeError(f"PAT approval failed ({resp.status}): {body[:300]}")


async def _wait_for_token_ws(url: str, request_id: str) -> dict[str, Any]:
    """Subscribe to createdAuthenticationToken via websocket."""
    ws_url = url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/ws/graphql"

    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(ws_url) as ws:
            # Send subscription
            await ws.send_json({
                "id": "1",
                "type": "start",
                "payload": {
                    "query": CREATED_TOKEN_SUB,
                    "variables": {"requestId": request_id},
                },
            })

            # Wait for data
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "data":
                        payload = data.get("payload", {}).get("data", {}).get("createdAuthenticationToken", {})
                        if payload.get("token"):
                            return payload["token"]
                        if payload.get("error"):
                            raise RuntimeError(f"Auth error: {payload['error']}")
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    break

    raise RuntimeError("WebSocket closed without receiving token")


async def _do_device_flow(url: str, pat: str) -> None:
    """Full device code flow: start → approve → wait for token."""
    global _access_token, _refresh_token, _expires_at

    # Step 1: Start auth flow
    data = await _gql_raw(url, START_AUTH_FLOW)
    payload = data.get("startAuthenticationFlow", {})
    if payload.get("error"):
        raise RuntimeError(f"Auth flow start error: {payload['error']}")

    request = payload.get("request", {})
    user_code = request.get("userCode")
    request_id = request.get("id")

    if not user_code or not request_id:
        raise RuntimeError(f"Missing userCode/requestId in auth response: {payload}")

    logger.info("Caido auth: approving device code %s", user_code)

    # Step 2: Approve via caido.io
    await _approve_via_cloud(pat, user_code)

    # Step 3: Wait for token via websocket
    token = await _wait_for_token_ws(url, request_id)

    _access_token = token.get("accessToken")
    _refresh_token = token.get("refreshToken")
    expires_str = token.get("expiresAt")
    if expires_str:
        _expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))

    _save_cached_token()
    logger.info("Caido auth: token acquired, expires at %s", _expires_at)


async def _do_token_refresh(url: str) -> bool:
    """Refresh the access token using the refresh token."""
    global _access_token, _refresh_token, _expires_at

    if not _refresh_token:
        return False

    try:
        data = await _gql_raw(url, REFRESH_TOKEN, {"refreshToken": _refresh_token})
        payload = data.get("refreshAuthenticationToken", {})
        if payload.get("error"):
            logger.warning("Token refresh error: %s", payload["error"])
            return False

        token = payload.get("token", {})
        _access_token = token.get("accessToken")
        _refresh_token = token.get("refreshToken") or _refresh_token
        expires_str = token.get("expiresAt")
        if expires_str:
            _expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        _save_cached_token()
        return True
    except Exception as exc:
        logger.warning("Token refresh failed: %s", exc)
        return False


# ── session management ─────────────────────────────────────────────────

def _is_session_stale() -> bool:
    """Check if the cached session is stale (closed or different event loop)."""
    global _session, _current_loop
    if _session is None:
        return False
    if _session.closed:
        return True
    try:
        current_loop = asyncio.get_running_loop()
        if _current_loop is not current_loop:
            return True
        if current_loop.is_closed():
            return True
    except RuntimeError:
        # No running loop — session is stale
        return True
    return False


async def _close_session() -> None:
    """Close the cached session if it exists."""
    global _session, _current_loop
    if _session and not _session.closed:
        try:
            await _session.close()
        except Exception:
            pass
    _session = None
    _current_loop = None


async def _ensure_auth() -> tuple[str, str]:
    """Ensure we have a valid access token. Returns (url, access_token)."""
    global _url, _access_token

    _url = _resolve_url()

    # Try cached token
    if _load_cached_token() and _access_token:
        return _url, _access_token

    # Try refresh
    if _refresh_token and await _do_token_refresh(_url) and _access_token:
        return _url, _access_token

    # Full device code flow
    pat = _resolve_pat()
    await _do_device_flow(_url, pat)
    if not _access_token:
        raise RuntimeError("Failed to acquire access token")
    return _url, _access_token


async def _get_session() -> tuple[aiohttp.ClientSession, str]:
    global _session, _url, _access_token, _current_loop

    url, token = await _ensure_auth()

    # Close stale session (different event loop or closed)
    if _is_session_stale():
        await _close_session()

    if _session and not _session.closed:
        _session.headers.update({"Authorization": f"Bearer {token}"})
        return _session, url

    _session = aiohttp.ClientSession(
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    _current_loop = asyncio.get_running_loop()
    return _session, url


# ── API calls ──────────────────────────────────────────────────────────

async def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query/mutation against the Caido API."""
    global _session, _current_loop

    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    for attempt in range(2):
        session, url = await _get_session()
        try:
            async with session.post(f"{url}/graphql", json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"GraphQL HTTP {resp.status}: {text[:500]}")
                data = await resp.json()
                if "errors" in data:
                    raise RuntimeError(f"GraphQL errors: {data['errors']}")
                return data.get("data", {})
        except (RuntimeError, aiohttp.ClientError) as e:
            error_str = str(e).lower()
            # Stale session or connection error — force new session and retry
            if attempt == 0 and any(kw in error_str for kw in [
                "timeout context manager", "event loop is closed",
                "connection reset", "session is closed",
            ]):
                await _close_session()
                continue
            raise
    # Should not reach here, but just in case
    raise RuntimeError("graphql: failed after 2 attempts")


async def health() -> dict[str, Any]:
    """Check Caido health via GraphQL."""
    try:
        data = await graphql("query { requests(first: 1) { edges { node { id } } } }")
        return {"status": "ok", "graphql": True}
    except Exception as e:
        # Try a simple HTTP GET as fallback
        try:
            session, url = await _get_session()
            async with session.get(f"{url}/") as resp:
                return {"status": "ok" if resp.status == 200 else "error", "statusCode": resp.status}
        except Exception:
            return {"status": "error", "error": str(e)}


async def close() -> None:
    """Close the shared session."""
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None
