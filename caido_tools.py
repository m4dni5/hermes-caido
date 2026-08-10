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
from graphql.auth import setup as _auth_setup
from graphql.client import health, graphql
from output import format_entry_compact, format_response

import asyncio
import os
import subprocess as _subprocess


async def _setup_via_subprocess(pat: str | None = None, url: str | None = None) -> dict:
    """Run the auth flow in an isolated subprocess.

    The Hermes agent's async context interferes with aiohttp WebSocket
    connections (inherited SSL state, nested event loops). Running the
    auth flow in a fresh process avoids this entirely.
    """
    if not pat or not url:
        return {"error": "PAT and URL are required for setup"}

    plugin_dir = str(Path(__file__).parent)
    helper = Path(__file__).parent / "auth_helper.py"

    if not helper.exists():
        return {"error": f"Auth helper not found: {helper}"}

    # Find the Python with aiohttp installed — same one running this plugin
    venv_python = sys.executable

    try:
        proc = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _subprocess.run(
                [venv_python, str(helper), pat, url],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=plugin_dir,
            ),
        )
    except _subprocess.TimeoutExpired:
        return {"error": "Auth flow timed out (60s)"}
    except Exception as e:
        return {"error": f"Failed to run auth helper: {e}"}

    if proc.returncode != 0:
        # Try to parse JSON error from stdout
        try:
            return json.loads(proc.stdout.strip())
        except Exception:
            return {"error": f"Auth helper failed (exit {proc.returncode}): {proc.stderr[:500]}"}

    try:
        result = json.loads(proc.stdout.strip())
    except Exception:
        return {"error": f"Auth helper returned invalid JSON: {proc.stdout[:200]}"}

    # Reload the cached token into the running process
    from graphql.client import _load_cached_token
    os.environ["CAIDO_PAT"] = pat
    os.environ["CAIDO_URL"] = url
    _load_cached_token()

    return result


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
        if result.get("status") != "ok":
            result["message"] = (
                "Caido instance is not healthy. Check that it is running. "
                "Run caido_auth_setup if this is an auth issue."
            )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "message": (
                "Health check failed. Run caido_auth_setup "
                "to configure credentials, or check that the Caido instance is running."
            ),
        }, indent=2)


async def handle_auth_setup(args: dict, **kwargs) -> str:
    """Run the device-code auth flow in an isolated subprocess."""
    try:
        pat = args.get("pat") or os.environ.get("CAIDO_PAT") or ""
        url = args.get("url") or os.environ.get("CAIDO_URL") or ""
        if not pat or not url:
            return json.dumps({
                "error": "PAT and URL are required for auth setup. Pass them explicitly, "
                         "or set CAIDO_PAT / CAIDO_URL in the environment.",
                "message": "Run caido_auth_setup to configure credentials.",
            }, indent=2)
        result = await _setup_via_subprocess(pat=pat, url=url)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


async def handle_export_curl(args: dict, **kwargs) -> str:
    try:
        data = await export_curl(request_id=args["request_id"])
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


async def handle_replay(args: dict, **kwargs) -> str:
    try:
        from graphql.replay import replay as replay_request, replay_with_edit

        request_id = args["request_id"]
        has_edits = any(k in args for k in ("path", "method", "headers", "body"))
        if has_edits:
            result = await replay_with_edit(
                request_id=request_id,
                path=args.get("path"),
                method=args.get("method"),
                headers=args.get("headers"),
                body=args.get("body"),
                session_name=args.get("session_name"),
            )
        else:
            result = await replay_request(request_id=request_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


async def handle_automate(args: dict, **kwargs) -> str:
    """One-call automate orchestration: source + target + payloads → running task."""
    try:
        from graphql.automate import (
            create_session as automate_create_session,
            rename_session as automate_rename_session,
            update_session as automate_update_session,
            start_task as automate_start_task,
        )
        from graphql.http_requests import get as get_request
        from placeholders import find_value
        from payloads import build_payload_input, validate_payload_config

        request_id = args["request_id"]
        target = args["target"]
        payloads = args.get("payloads", [])
        strategy = args.get("strategy", "ALL")
        session_name = args.get("session_name")

        if not payloads:
            return json.dumps({"error": "payloads must be a non-empty list"}, indent=2)

        # 1. Fetch the source request (get() resolves UI metadata ids too)
        req = await get_request(request_id=request_id)
        if "error" in req:
            return json.dumps(req, indent=2)
        raw = req.get("requestRaw", "")
        if not raw:
            return json.dumps({"error": f"Request {request_id!r} has no raw bytes"}, indent=2)

        # 2. Embed the FUZZ slot
        if target not in raw:
            return json.dumps({
                "error": f"Target {target!r} not found in raw request. "
                         f"The value must appear literally in the request (path, query, headers, or body).",
            }, indent=2)
        template = raw.replace(target, "FUZZ", 1)

        # 3. Locate the placeholder byte range
        ranges = find_value(template, "FUZZ")
        if not ranges:
            return json.dumps({"error": "FUZZ placeholder not found after substitution"}, indent=2)

        # 4. Validate payload config against strategy (1 placeholder for ALL/SEQUENTIAL)
        try:
            validate_payload_config(strategy, num_placeholders=1, payload_sets=[payloads])
        except Exception as e:
            return json.dumps({"error": f"Payload config invalid: {e}"}, indent=2)

        # 5. Create the automate session seeded from the request
        session = await automate_create_session(request_id=request_id)
        if "error" in session:
            return json.dumps(session, indent=2)
        session_id = session["id"]
        if session_name:
            rename = await automate_rename_session(session_id, session_name)
            if "error" in rename:
                return json.dumps(rename, indent=2)

        # 6. Configure raw + placeholder + payloads + strategy
        connection = {
            "host": req.get("host", ""),
            "port": req.get("port", 443),
            "isTLS": req.get("isTls", True),
        }
        settings = {
            "placeholders": ranges,
            "payloads": build_payload_input([payloads]),
            "strategy": strategy,
        }
        updated = await automate_update_session(
            session_id,
            raw=template,
            connection=connection,
            settings=settings,
        )
        if "error" in updated:
            return json.dumps(updated, indent=2)

        # 7. Start the task
        task = await automate_start_task(session_id)
        if "error" in task:
            return json.dumps(task, indent=2)

        return json.dumps({
            "session_id": session_id,
            "task_id": task.get("taskId"),
            "entry_id": task.get("entryId"),
            "strategy": strategy,
            "placeholder": ranges,
            "status": "started",
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


async def handle_automate_status(args: dict, **kwargs) -> str:
    try:
        from graphql.automate import list_tasks as automate_list_tasks

        task_id = args["task_id"]
        tasks = await automate_list_tasks(limit=100)
        for t in tasks:
            if t.get("id") == task_id:
                return json.dumps(t, indent=2)
        return json.dumps({"task_id": task_id, "status": "not_found"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ---------------------------------------------------------------------------
# Onboard handler — full context in one call
# ---------------------------------------------------------------------------

_ONBOARD_QUERY = """\
query Onboard {
    currentProject {
        readOnly
        project { id name status temporary createdAt updatedAt size }
    }
    interceptOptions {
        request { enabled }
        response { enabled }
        scope { scopeId }
    }
    scopes { id name allowlist denylist }
    findings { count { value } }
}"""


async def handle_onboard(args: dict, **kwargs) -> str:
    """Gather full Caido context in one call."""
    try:
        # Layer 1: Health check
        health_ok = False
        try:
            h = await health()
            health_ok = h.get("status") == "ok"
        except Exception:
            pass

        if not health_ok:
            return json.dumps({
                "health": {"status": "unreachable"},
                "message": (
                    "Cannot reach Caido instance. Check that it is running and the URL is correct. "
                    "Run caido_auth_setup to configure credentials."
                ),
            }, indent=2)

        # Layer 2: Auth check — try a simple query
        auth_ok = False
        auth_error = None
        try:
            data = await graphql(_ONBOARD_QUERY)
            auth_ok = True
        except Exception as e:
            auth_error = str(e)
            data = {}

        if not auth_ok:
            return json.dumps({
                "health": {"status": "ok"},
                "auth": {"authenticated": False, "error": auth_error},
                "message": (
                    "Not authenticated. Run caido_auth_setup "
                    "to configure credentials."
                ),
            }, indent=2)

        # Layer 3: Parse results
        project_data = data.get("currentProject", {})
        project = project_data.get("project", {})
        intercept = data.get("interceptOptions", {})
        scopes = data.get("scopes", [])
        findings_count = (data.get("findings") or {}).get("count", {}).get("value", 0)

        # Layer 4: Recent traffic summary (lightweight)
        recent_hosts = []
        recent_count = 0
        try:
            recent_result = await search(query="", limit=50, sort="createdAt", order="DESC")
            entries = recent_result.get("entries", [])
            recent_count = len(entries)
            recent_hosts = list({e["host"] for e in entries if "host" in e})[:10]
        except Exception:
            pass

        # Layer 4b: Suggest scope by matching recent hosts against scope allowlists
        suggested_scope = None
        if recent_hosts and scopes:
            from fnmatch import fnmatch
            best_score = 0
            for scope in scopes:
                allowlist = scope.get("allowlist", [])
                score = sum(
                    1 for host in recent_hosts
                    for pattern in allowlist
                    if fnmatch(host, pattern) or fnmatch(host, f"*{pattern}*") or host == pattern
                )
                if score > best_score:
                    best_score = score
                    suggested_scope = {"id": scope["id"], "name": scope["name"], "matched_hosts": [
                        host for host in recent_hosts
                        for pattern in allowlist
                        if fnmatch(host, pattern) or fnmatch(host, f"*{pattern}*") or host == pattern
                    ]}

        # Layer 5: Hosted files
        hosted = []
        try:
            files = await hosted_files()
            hosted = [f["name"] for f in files if isinstance(f, dict) and "name" in f]
        except Exception:
            pass

        # Set the suggested scope as active for subsequent search/recent calls
        if suggested_scope:
            from graphql.http_requests import set_active_scope
            set_active_scope(suggested_scope["id"])

        return json.dumps({
            "health": {"status": "ok"},
            "auth": {"authenticated": True},
            "project": {
                "name": project.get("name"),
                "id": project.get("id"),
                "status": project.get("status"),
                "size_mb": round(project.get("size", 0) / 1024 / 1024, 1),
            },
            "scopes": [
                {"id": s["id"], "name": s["name"], "allowlist": s.get("allowlist", [])}
                for s in scopes
            ],
            "intercept": {
                "request": intercept.get("request", {}).get("enabled"),
                "response": intercept.get("response", {}).get("enabled"),
                "scope_id": (intercept.get("scope") or {}).get("scopeId"),
            },
            "suggested_scope": suggested_scope,
            "recent": {"count": recent_count, "hosts": recent_hosts},
            "findings_count": findings_count,
            "hosted_files": hosted,
        }, indent=2)

    except Exception as e:
        error_str = str(e)
        result = {"error": error_str}
        if any(kw in error_str.lower() for kw in ["auth", "token", "pat", "401", "403", "forbidden"]):
            result["message"] = (
                "Run caido_auth_setup to configure credentials."
            )
        return json.dumps(result, indent=2)
