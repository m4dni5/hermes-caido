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
from graphql.client import health, graphql
from output import format_entry_compact, format_response

import asyncio
import json as _json
import subprocess as _subprocess
from pathlib import Path as _Path


async def _setup_via_subprocess(pat: str | None = None, url: str | None = None) -> dict:
    """Run the auth flow in an isolated subprocess.

    The Hermes agent's async context interferes with aiohttp WebSocket
    connections (inherited SSL state, nested event loops). Running the
    auth flow in a fresh process avoids this entirely.
    """
    if not pat or not url:
        return {"error": "PAT and URL are required for setup"}

    plugin_dir = str(_Path(__file__).parent)
    helper = _Path(__file__).parent / "auth_helper.py"

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
            return _json.loads(proc.stdout.strip())
        except Exception:
            return {"error": f"Auth helper failed (exit {proc.returncode}): {proc.stderr[:500]}"}

    try:
        result = _json.loads(proc.stdout.strip())
    except Exception:
        return {"error": f"Auth helper returned invalid JSON: {proc.stdout[:200]}"}

    # Reload the cached token into the running process
    import os
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
            # File-based clear — no async needed
            cleared = []
            import os
            hermes_home = os.environ.get("HERMES_HOME") or str(_Path.home() / ".hermes")
            cache = _Path(hermes_home) / "cache" / "caido-token.json"
            if cache.exists():
                cache.unlink()
                cleared.append(str(cache))
            secrets = _Path.home() / ".claude" / "config" / "secrets.json"
            if secrets.exists():
                try:
                    import json as _j
                    data = _j.loads(secrets.read_text())
                    if "caido" in data and "cachedToken" in data["caido"]:
                        del data["caido"]["cachedToken"]
                        secrets.write_text(_j.dumps(data, indent=2))
                        cleared.append(f"{secrets} (cachedToken)")
                except Exception:
                    pass
            result = {"cleared": cleared, "message": "Cache cleared. Next call will trigger fresh auth."}
        elif action == "setup":
            result = await _setup_via_subprocess(
                pat=args.get("pat"),
                url=args.get("url"),
            )
        else:
            result = {"error": f"Unknown action: {action}"}
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


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
                "message": "Cannot reach Caido instance. Check connection and run caido_setup.",
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
                "message": "Not authenticated. Load caido:utils and run setup.",
            }, indent=2)

        # Layer 3: Parse results
        project_data = data.get("currentProject", {})
        project = project_data.get("project", {})
        intercept = data.get("interceptOptions", {})
        scopes = data.get("scopes", [])
        findings_count = data.get("findings", {}).get("count", {}).get("value", 0)

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
                "scope_id": intercept.get("scope", {}).get("scopeId"),
            },
            "suggested_scope": suggested_scope,
            "recent": {"count": recent_count, "hosts": recent_hosts},
            "findings_count": findings_count,
            "hosted_files": hosted,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})
