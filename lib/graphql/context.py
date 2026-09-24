"""One-shot session context envelope — first Caido call orients the agent.

Replaces the old mandatory ``caido_onboard`` gate. The first successful
read tool call (search/recent/get) runs a lightweight context query in
addition to the requested operation, resolves the active scope from
recent traffic, and attaches a ``context`` block to that one response.
Subsequent calls skip it entirely — zero added latency after the first.

Deliberately never raises: a context failure must not fail the tool call
the agent actually asked for. Auth errors mark the envelope as done (the
agent will see the auth error from the operation itself and run
caido_auth_setup; retrying the context query adds nothing). Other errors
are retried up to _MAX_ATTEMPTS times across later calls.
"""

from __future__ import annotations

import logging
from fnmatch import fnmatch
from typing import Any

from .client import graphql
from .http_requests import search, set_active_scope

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3

_CONTEXT_QUERY = """\
query Context {
    currentProject { project { id name status size } }
    scopes { id name allowlist }
}
"""

# Module state: _sent means the envelope was delivered (or permanently
# given up on); _attempts bounds retries on transient failures.
_sent: bool = False
_attempts: int = 0
_context: dict[str, Any] | None = None


def get_session_context() -> dict[str, Any] | None:
    """Return the delivered context block, or None if not yet delivered."""
    return _context if _sent else None


def reset_session_context() -> None:
    """Clear envelope state (used by tests and after scope changes)."""
    global _sent, _attempts, _context
    _sent = False
    _attempts = 0
    _context = None


def _suggest_scope(
    scopes: list[dict[str, Any]], hosts: list[str]
) -> dict[str, Any] | None:
    """Match recent-traffic hosts against scope allowlists (fnmatch globs).

    Returns the best-matching scope with its matched hosts, or None when
    nothing matches or the match is ambiguous (tie between scopes).
    """
    if not hosts or not scopes:
        return None
    scores: dict[str, tuple[int, list[str]]] = {}
    for scope in scopes:
        allowlist = scope.get("allowlist") or []
        matched = sorted({
            host
            for host in hosts
            for pattern in allowlist
            if fnmatch(host, pattern) or fnmatch(host, f"*{pattern}*") or host == pattern
        })
        if matched:
            scores[scope["id"]] = (len(matched), matched)
    if not scores:
        return None
    best = max(scores.values(), key=lambda v: v[0])
    winners = [sid for sid, v in scores.items() if v[0] == best[0]]
    if len(winners) > 1:
        return None  # ambiguous — don't guess
    scope = next(s for s in scopes if s["id"] == winners[0])
    return {
        "id": scope["id"],
        "name": scope["name"],
        "matched_hosts": best[1],
    }


async def ensure_context(client: Any = None) -> dict[str, Any] | None:
    """Run the one-shot context envelope.

    Returns the context block on the call that produced it (and only that
    call); returns None on every subsequent call. Never raises.
    """
    global _sent, _attempts, _context
    if _sent or _attempts >= _MAX_ATTEMPTS:
        return None
    _attempts += 1
    try:
        data = await (client or graphql)(_CONTEXT_QUERY)
        project_data = data.get("currentProject") or {}
        project = project_data.get("project") or {}
        scopes = data.get("scopes") or []

        # Recent-traffic hosts — unfiltered read so the suggestion sees
        # everything, not just whatever scope happens to be set.
        hosts: list[str] = []
        try:
            recent = await search(
                query="", limit=25, sort="createdAt", order="DESC",
                scope_id=None, client=client,
            )
            hosts = list({e["host"] for e in recent.get("entries", []) if "host" in e})[:10]
        except Exception:
            pass

        suggestion = _suggest_scope(scopes, hosts)
        active_scope = None
        if suggestion:
            set_active_scope(suggestion["id"])
            active_scope = suggestion["id"]

        _context = {
            "note": (
                "One-time session context. A scope was auto-selected from "
                "recent traffic — pass scope_id=\"\" to see all history, or "
                "a scope id to override. Full guidance: skill_view(\"caido:caido\")."
            ),
            "project": {
                "name": project.get("name"),
                "id": project.get("id"),
                "status": project.get("status"),
            },
            "active_scope": active_scope,
            "suggested_scope": suggestion,
            "scopes": [
                {"id": s.get("id"), "name": s.get("name"), "allowlist": s.get("allowlist") or []}
                for s in scopes
            ],
            "recent_hosts": hosts,
        }
        _sent = True
        return _context
    except Exception as exc:
        error_str = str(exc)
        if any(kw in error_str.lower() for kw in ["auth", "token", "pat", "401", "403", "forbidden"]):
            # Auth errors repeat on every call until fixed — don't burn
            # attempts or latency on a query that can't succeed yet.
            _sent = True
            logger.debug("Context envelope skipped (auth error): %s", error_str)
        else:
            logger.debug("Context envelope deferred: %s", error_str)
        return None
