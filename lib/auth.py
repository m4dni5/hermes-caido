"""Caido auth and setup helpers.

Provides setup, auth_status, clear_cache, and test_connection functions
for diagnosing and fixing Caido authentication issues.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client import (
    _HERMES_ENV, _CLAUDE_SECRETS, _TOKEN_CACHE,
    _resolve_pat, _resolve_url, _load_cached_token,
    _save_cached_token, _do_device_flow,
    graphql, health,
    close as close_client,
)

# ── Public API ─────────────────────────────────────────────────────────────


async def auth_status() -> dict:
    """Check current authentication status.

    Returns:
        Dict with auth state, token info, and connection test results.
    """
    result = {
        "pat_source": None,
        "url_source": None,
        "token_cached": False,
        "token_expired": None,
        "token_expires_at": None,
        "connection_ok": False,
        "graphql_ok": False,
        "error": None,
    }

    # Check PAT source
    pat = os.environ.get("CAIDO_PAT")
    if pat:
        result["pat_source"] = "env:CAIDO_PAT"
    elif _HERMES_ENV.is_file():
        try:
            for line in _HERMES_ENV.read_text().splitlines():
                if line.strip().startswith("CAIDO_PAT"):
                    result["pat_source"] = f"file:{_HERMES_ENV}"
                    break
        except Exception:
            pass
    if not result["pat_source"] and _CLAUDE_SECRETS.is_file():
        try:
            secrets = json.loads(_CLAUDE_SECRETS.read_text())
            if secrets.get("caido", {}).get("pat"):
                result["pat_source"] = f"file:{_CLAUDE_SECRETS}"
        except Exception:
            pass

    # Check URL source
    url = os.environ.get("CAIDO_URL")
    if url:
        result["url_source"] = "env:CAIDO_URL"
    elif _HERMES_ENV.is_file():
        try:
            for line in _HERMES_ENV.read_text().splitlines():
                if line.strip().startswith("CAIDO_URL"):
                    result["url_source"] = f"file:{_HERMES_ENV}"
                    break
        except Exception:
            pass
    if not result["url_source"] and _CLAUDE_SECRETS.is_file():
        try:
            secrets = json.loads(_CLAUDE_SECRETS.read_text())
            if secrets.get("caido", {}).get("url"):
                result["url_source"] = f"file:{_CLAUDE_SECRETS}"
        except Exception:
            pass

    # Check token cache
    from datetime import datetime, timezone
    for cache_path in [_TOKEN_CACHE, _CLAUDE_SECRETS]:
        if not cache_path.is_file():
            continue
        try:
            data = json.loads(cache_path.read_text())
            if cache_path == _CLAUDE_SECRETS:
                data = data.get("caido", {}).get("cachedToken", {})
            token = data.get("accessToken") or data.get("access_token")
            if token:
                result["token_cached"] = True
                expires_str = data.get("expiresAt") or data.get("expires_at")
                if expires_str:
                    expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    result["token_expires_at"] = expires_at.isoformat()
                    result["token_expired"] = expires_at <= datetime.now(timezone.utc)
                break
        except Exception:
            continue

    # Test connection
    try:
        health_data = await health()
        result["connection_ok"] = health_data.get("status") == "ok"
    except Exception as e:
        result["error"] = f"Connection failed: {e}"
        return result

    # Test GraphQL (requires valid token)
    try:
        data = await graphql("query { requests(first: 1) { edges { node { id } } } }")
        result["graphql_ok"] = bool(data.get("requests", {}).get("edges"))
    except Exception as e:
        result["error"] = f"GraphQL auth failed: {e}"

    return result


async def clear_cache() -> dict:
    """Clear the token cache and close the client session.

    Forces a fresh authentication on the next GraphQL call.

    Returns:
        Dict with cleared cache paths.
    """
    cleared = []

    # Close existing session
    await close_client()

    # Clear token cache
    if _TOKEN_CACHE.is_file():
        _TOKEN_CACHE.unlink()
        cleared.append(str(_TOKEN_CACHE))

    # Clear cached token from secrets.json
    if _CLAUDE_SECRETS.is_file():
        try:
            data = json.loads(_CLAUDE_SECRETS.read_text())
            if "caido" in data and "cachedToken" in data["caido"]:
                del data["caido"]["cachedToken"]
                _CLAUDE_SECRETS.write_text(json.dumps(data, indent=2))
                cleared.append(f"{_CLAUDE_SECRETS} (cachedToken)")
        except Exception as e:
            return {"error": f"Failed to clear secrets.json: {e}", "cleared": cleared}

    return {"cleared": cleared, "message": "Cache cleared. Next GraphQL call will trigger fresh auth."}


async def test_connection() -> dict:
    """Test full connectivity: health, auth, and a simple query.

    Returns:
        Dict with test results for each layer.
    """
    results = {
        "health": False,
        "auth": False,
        "query": False,
        "error": None,
    }

    # Layer 1: Health (no auth required)
    try:
        health_data = await health()
        results["health"] = health_data.get("status") == "ok"
    except Exception as e:
        results["error"] = f"Health check failed: {e}"
        return results

    # Layer 2: Auth (GraphQL with auth)
    try:
        data = await graphql("query { requests(first: 1) { edges { node { id } } } }")
        results["auth"] = bool(data.get("requests", {}).get("edges"))
    except Exception as e:
        results["error"] = f"Auth failed: {e}"
        return results

    # Layer 3: Query (actual data fetch)
    try:
        data = await graphql("query { requests(first: 1) { edges { node { id } } } }")
        results["query"] = True
    except Exception as e:
        results["error"] = f"Query failed: {e}"

    return results


async def setup(pat: str | None = None, url: str | None = None) -> dict:
    """Set up Caido credentials.

    Args:
        pat: Caido Personal Access Token. If None, reads from env/file.
        url: Caido instance URL. If None, reads from env/file.

    Returns:
        Dict with setup results and next steps.
    """
    result = {
        "pat_set": False,
        "url_set": False,
        "auth_flow": None,
        "error": None,
    }

    # Set PAT
    if pat:
        os.environ["CAIDO_PAT"] = pat
        result["pat_set"] = True
    else:
        try:
            _resolve_pat()
            result["pat_set"] = True
        except RuntimeError as e:
            result["error"] = f"PAT not found: {e}"
            return result

    # Set URL
    if url:
        os.environ["CAIDO_URL"] = url
        result["url_set"] = True
    else:
        try:
            _resolve_url()
            result["url_set"] = True
        except RuntimeError as e:
            result["error"] = f"URL not found: {e}"
            return result

    # Clear cache and trigger fresh auth
    await clear_cache()

    # Try auth flow
    try:
        pat_resolved = _resolve_pat()
        url_resolved = _resolve_url()
        await _do_device_flow(url_resolved, pat_resolved)
        result["auth_flow"] = "success"
    except Exception as e:
        result["auth_flow"] = "failed"
        result["error"] = f"Auth flow failed: {e}"
        return result

    # Verify
    try:
        data = await graphql("query { requests(first: 1) { edges { node { id } } } }")
        result["verified"] = bool(data.get("requests", {}).get("edges"))
    except Exception as e:
        result["verified"] = False
        result["error"] = f"Verification failed: {e}"

    return result
