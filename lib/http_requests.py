"""Caido HTTP request operations — sync wrappers.

Usage:
    import http_requests
    results = http_requests.search(query='req.path.cont:"/api/"')
    req = http_requests.get(request_id="123")
"""

from __future__ import annotations
from typing import Any
from sync import sync_run
from graphql.http_requests import (
    search as _search,
    recent as _recent,
    get as _get,
    get_response as _get_response,
    export_curl as _export_curl,
)


def search(query: str = "", limit: int = 20, sort: str | None = None, order: str | None = None, scope_id: Any = None) -> dict:
    """Search proxy history with HTTPQL.

    Args:
        scope_id: Scope ID to filter by. Defaults to active Caido scope.
            Pass None to use active scope, or "" to disable filtering.
    """
    return sync_run(_search, query=query, limit=limit, sort=sort, order=order, scope_id=scope_id)


def recent(limit: int = 20, scope_id: Any = None) -> dict:
    """Get recent intercepted requests."""
    return sync_run(_recent, limit=limit, scope_id=scope_id)


def get(request_id: str) -> dict:
    """Get request/response by ID."""
    return sync_run(_get, request_id=request_id)


def get_response(request_id: str) -> dict:
    """Get response only."""
    return sync_run(_get_response, request_id=request_id)


def export_curl(request_id: str) -> dict:
    """Export request as curl command."""
    return sync_run(_export_curl, request_id=request_id)
