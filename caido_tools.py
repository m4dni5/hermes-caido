"""Async tool handlers for Hermes Agent Caido plugin."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from graphql.http_requests import search, recent, get, get_response, export_curl
from graphql.replay import (
    replay, sessions, create_session, collections,
    rename_session, delete_sessions,
)
from graphql.findings import list_findings, get_finding, create_finding, update_finding
from graphql.management import (
    scopes, get_scope, create_scope, delete_scope,
    filters, create_filter, delete_filter,
    environments, create_environment, delete_environment,
    projects, create_project, delete_project,
    hosted_files, tasks, cancel_task,
)
from graphql.auth import auth_status, clear_cache, test_connection, setup
from graphql.client import health
from output import format_entry_compact, format_response


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format(data: dict, args: dict) -> str:
    """Apply formatting based on args flags."""
    if args.get("raw"):
        return format_response(data, raw=True)
    if args.get("headers_only"):
        return format_response(data, headers_only=True)
    if args.get("compact"):
        # Handle search results (dict with entries key)
        entries = data.get("entries", [data]) if isinstance(data, dict) else data
        if isinstance(entries, list):
            return "\n".join(format_entry_compact(e) for e in entries)
        return format_entry_compact(entries)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_search(args: dict, **kwargs) -> str:
    try:
        data = await search(
            query=args["query"],
            limit=args.get("limit", 20),
            sort=args.get("sort"),
            order=args.get("order"),
        )
        return _format(data, args)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_recent(args: dict, **kwargs) -> str:
    try:
        data = await recent(limit=args.get("limit", 20))
        return _format(data, args)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_get(args: dict, **kwargs) -> str:
    try:
        data = await get(request_id=args["request_id"])
        return _format(data, args)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_findings(args: dict, **kwargs) -> str:
    try:
        data = await list_findings(
            query=args.get("query"),
            limit=args.get("limit", 50),
        )
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_create_finding(args: dict, **kwargs) -> str:
    try:
        result = await create_finding(
            title=args["title"],
            description=args.get("description"),
            severity=args.get("severity"),
            request_id=args.get("request_id"),
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_health(args: dict, **kwargs) -> str:
    try:
        result = await health()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_setup(args: dict, **kwargs) -> str:
    try:
        action = args.get("action", "status")
        if action == "status":
            result = await auth_status()
        elif action == "test":
            result = await test_connection()
        elif action == "clear":
            result = await clear_cache()
        elif action == "setup":
            result = await setup(
                pat=args.get("pat"),
                url=args.get("url"),
            )
        else:
            result = {"error": f"Unknown action: {action}"}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
