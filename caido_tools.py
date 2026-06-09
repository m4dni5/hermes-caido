"""Async tool handlers for Hermes Agent Caido plugin."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from http_requests import search, recent, get, get_response, export_curl
from replay import (
    replay, sessions, create_session, collections,
    rename_session, delete_sessions,
)
from findings import list_findings, get_finding, create_finding, update_finding
from management import (
    scopes, get_scope, create_scope, delete_scope,
    filters, create_filter, delete_filter,
    environments, create_environment, delete_environment,
    projects, create_project, delete_project,
    hosted_files, tasks, cancel_task,
)
from output import format_response, format_entry_compact, truncate_body, extract_headers, format_curl
from client import health as client_health


def _format(data: dict, args: dict) -> str:
    """Apply formatting based on args flags."""
    # For search/recent results, format the entries list
    if isinstance(data, dict) and "entries" in data:
        entries = data["entries"]
        if args.get("compact"):
            return format_response(entries, compact=True)
        if args.get("headers_only"):
            return format_response(entries, headers_only=True)
        if args.get("raw"):
            return format_response(data, raw=True)
        return json.dumps(data)
    # For other data
    if args.get("raw"):
        return format_response(data, raw=True)
    if args.get("headers_only"):
        return format_response(data, headers_only=True)
    if args.get("compact"):
        return format_response(data, compact=True)
    return json.dumps(data)


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
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_create_finding(args: dict, **kwargs) -> str:
    try:
        data = await create_finding(
            title=args["title"],
            description=args.get("description"),
            severity=args.get("severity"),
            request_id=args.get("request_id"),
        )
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_scopes(args: dict, **kwargs) -> str:
    try:
        data = await scopes(limit=args.get("limit", 50))
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_filters(args: dict, **kwargs) -> str:
    try:
        data = await filters(limit=args.get("limit", 50))
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_envs(args: dict, **kwargs) -> str:
    try:
        data = await environments(limit=args.get("limit", 50))
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_projects(args: dict, **kwargs) -> str:
    try:
        data = await projects(limit=args.get("limit", 50))
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_health(args: dict, **kwargs) -> str:
    try:
        data = await client_health()
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_setup(args: dict, **kwargs) -> str:
    try:
        from auth import auth_status, clear_cache, test_connection, setup as setup_auth
        action = args.get("action", "status")
        if action == "status":
            data = await auth_status()
        elif action == "test":
            data = await test_connection()
        elif action == "clear":
            data = await clear_cache()
        elif action == "setup":
            data = await setup_auth(pat=args.get("pat"), url=args.get("url"))
        else:
            data = {"error": f"Unknown action: {action}"}
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})
