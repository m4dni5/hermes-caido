"""Unit tests for the one-shot session context envelope.

The envelope must: run exactly once, auto-select an unambiguous scope from
recent-traffic hosts, refuse to guess on ambiguous matches, never raise,
and skip auth-blocked sessions permanently (retrying a doomed query on
every call would double the failure latency of every tool call).
"""

from __future__ import annotations

import asyncio
import sys

from conftest import PLUGIN_DIR, _NS_PARENT


def _ctx_mod():
    import importlib

    return importlib.import_module(f"{_NS_PARENT}.caido.lib.graphql.context")


def _reset(mod) -> None:
    mod.reset_session_context()


def _fake_graphql(payload):
    async def graphql(query, variables=None):
        return payload
    return graphql


def _fake_search(entries):
    async def search(*args, **kwargs):
        return {"entries": entries, "total": len(entries)}
    return search


def test_envelope_runs_once_and_sets_scope(plugin) -> None:
    mod = _ctx_mod()
    _reset(mod)

    mod.graphql = _fake_graphql({
        "currentProject": {"project": {"id": "1", "name": "engagement", "status": "ACTIVE"}},
        "scopes": [{"id": "7", "name": "target", "allowlist": ["*.example.com"]}],
    })
    mod.search = _fake_search([
        {"host": "api.example.com"},
        {"host": "www.example.com"},
        {"host": "noise.randomcdn.net"},
    ])

    block = asyncio.run(mod.ensure_context())
    assert block is not None
    assert block["project"]["name"] == "engagement"
    assert block["active_scope"] == "7"
    assert block["suggested_scope"]["id"] == "7"
    assert "api.example.com" in block["suggested_scope"]["matched_hosts"]
    # The active scope was set for search/recent defaults.
    import importlib

    http_requests = importlib.import_module(
        f"{_NS_PARENT}.caido.lib.graphql.http_requests"
    )
    assert http_requests.get_active_scope() == "7"
    # Second call: envelope already delivered — no repeat, no cost.
    assert asyncio.run(mod.ensure_context()) is None
    _reset(mod)


def test_envelope_refuses_ambiguous_scope(plugin) -> None:
    mod = _ctx_mod()
    _reset(mod)

    mod.graphql = _fake_graphql({
        "currentProject": {"project": {"name": "engagement"}},
        "scopes": [
            {"id": "1", "name": "a", "allowlist": ["*.foo.com"]},
            {"id": "2", "name": "b", "allowlist": ["*.bar.com"]},
        ],
    })
    mod.search = _fake_search([{"host": "x.foo.com"}, {"host": "y.bar.com"}])

    block = asyncio.run(mod.ensure_context())
    assert block is not None
    assert block["suggested_scope"] is None
    assert block["active_scope"] is None
    _reset(mod)


def test_envelope_never_raises_on_auth_error(plugin) -> None:
    mod = _ctx_mod()
    _reset(mod)

    async def graphql(query, variables=None):
        raise RuntimeError("401 Unauthorized: invalid token")

    mod.graphql = graphql

    # Must not raise; must mark the session done so later calls don't retry.
    assert asyncio.run(mod.ensure_context()) is None
    assert asyncio.run(mod.ensure_context()) is None
    assert mod.get_session_context() is None
    _reset(mod)


def test_envelope_retries_transient_errors_within_budget(plugin) -> None:
    mod = _ctx_mod()
    _reset(mod)

    calls = {"n": 0}

    async def graphql(query, variables=None):
        calls["n"] += 1
        raise RuntimeError("connection reset")

    mod.graphql = graphql

    for _ in range(mod._MAX_ATTEMPTS + 2):
        asyncio.run(mod.ensure_context())
    assert calls["n"] == mod._MAX_ATTEMPTS
    _reset(mod)
