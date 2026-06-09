"""Async tool handlers for Hermes Agent Caido plugin."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from http_requests import search, recent, get, get_response, export_curl
from replay import (
    replay, send_raw, sessions, create_session, collections,
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


async def handle_replay_request(args: dict, **kwargs) -> str:
    try:
        data = await replay(request_id=args["request_id"])
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_send_raw(args: dict, **kwargs) -> str:
    try:
        data = await send_raw(
            raw_request=args["raw_request"],
            host=args["host"],
            port=args.get("port", 443),
            tls=args.get("tls", True),
            sni=args.get("sni"),
        )
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_replay_sessions(args: dict, **kwargs) -> str:
    try:
        data = await sessions(limit=args.get("limit", 50))
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_create_replay_session(args: dict, **kwargs) -> str:
    try:
        data = await create_session(
            name=args["name"],
            collection_id=args.get("collection_id"),
        )
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_rename_replay_session(args: dict, **kwargs) -> str:
    try:
        data = await rename_session(
            session_id=args["session_id"],
            name=args["name"],
        )
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_delete_replay_sessions(args: dict, **kwargs) -> str:
    try:
        data = await delete_sessions(ids=args["session_ids"])
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_replay_collections(args: dict, **kwargs) -> str:
    try:
        data = await collections(limit=args.get("limit", 50))
        return json.dumps(data)
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


async def handle_get_finding(args: dict, **kwargs) -> str:
    try:
        data = await get_finding(finding_id=args["finding_id"])
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


async def handle_update_finding(args: dict, **kwargs) -> str:
    try:
        data = await update_finding(
            finding_id=args["finding_id"],
            title=args.get("title"),
            description=args.get("description"),
            severity=args.get("severity"),
        )
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_export_curl(args: dict, **kwargs) -> str:
    try:
        data = await export_curl(request_id=args["request_id"])
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
