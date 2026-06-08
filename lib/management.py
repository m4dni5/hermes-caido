"""Management operations for the Caido Python SDK CLI.

Wraps the Caido SDK for scopes, filters, environments, projects, hosted
files, and tasks.  Every public async function accepts an optional ``client``
keyword; when omitted a shared client is obtained from ``lib.client``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from client import get_client  # noqa: E402


# ---------------------------------------------------------------------------
# SDK-object → plain-dict conversion helpers
# ---------------------------------------------------------------------------

def _scope_to_dict(scope: Any) -> dict[str, Any]:
    """Convert an SDK ``Scope`` to a plain dict."""
    return {
        "id": str(scope.id),
        "name": scope.name,
        "allowlist": list(scope.allowlist),
        "denylist": list(scope.denylist),
        "indexed": scope.indexed,
    }


def _filter_to_dict(fp: Any) -> dict[str, Any]:
    """Convert an SDK ``FilterPreset`` to a plain dict."""
    return {
        "id": str(fp.id),
        "name": fp.name,
        "alias": fp.alias,
        "clause": fp.clause,
        "kind": str(fp.kind),
    }


def _environment_to_dict(env: Any) -> dict[str, Any]:
    """Convert an SDK ``Environment`` to a plain dict."""
    return {
        "id": str(env.id),
        "name": env.name,
        "version": env.version,
        "variables": [
            {"name": v.name, "value": v.value, "kind": str(v.kind)}
            for v in env.variables
        ],
    }


def _project_to_dict(proj: Any) -> dict[str, Any]:
    """Convert an SDK ``Project`` to a plain dict."""
    return {
        "id": str(proj.id),
        "name": proj.name,
        "path": proj.path,
        "status": str(proj.status),
        "temporary": proj.temporary,
        "createdAt": proj.created_at.isoformat() if proj.created_at else None,
        "updatedAt": proj.updated_at.isoformat() if proj.updated_at else None,
        "version": proj.version,
        "size": proj.size,
        "readOnly": proj.read_only,
    }


def _hosted_file_to_dict(hf: Any) -> dict[str, Any]:
    """Convert an SDK ``HostedFile`` to a plain dict."""
    return {
        "id": str(hf.id),
        "name": hf.name,
        "path": hf.path,
        "size": hf.size,
        "status": str(hf.status),
        "createdAt": hf.created_at.isoformat() if hf.created_at else None,
        "updatedAt": hf.updated_at.isoformat() if hf.updated_at else None,
    }


def _task_to_dict(task: Any) -> dict[str, Any]:
    """Convert an SDK ``Task`` (or ``ReplayTask``) to a plain dict."""
    d: dict[str, Any] = {
        "id": str(task.id),
        "createdAt": task.created_at if hasattr(task, "created_at") else None,
        "type": "replay" if type(task).__name__ == "ReplayTask" else "task",
    }
    # ReplayTask carries a replay_entry_id
    if hasattr(task, "replay_entry_id"):
        d["replayEntryId"] = str(task.replay_entry_id)
    return d


# ---------------------------------------------------------------------------
# Scope operations
# ---------------------------------------------------------------------------

async def scopes(
    limit: int = 50,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """List scopes.

    Args:
        limit:  Maximum number of scopes to return (default 50).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of scope dicts.
    """
    try:
        c = client or await get_client()
        items = await c.scope.list()
        return [_scope_to_dict(s) for s in items[:limit]]
    except Exception as exc:
        return [{"error": str(exc)}]


async def get_scope(
    scope_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Get a scope by ID.

    Args:
        scope_id: The scope ID.
        client:   Optional pre-built Caido Client instance.

    Returns:
        Scope dict, or dict with ``error`` key on failure.
    """
    try:
        c = client or await get_client()
        scope = await c.scope.get(scope_id)
        if scope is None:
            return {"error": f"Scope {scope_id!r} not found"}
        return _scope_to_dict(scope)
    except Exception as exc:
        return {"error": str(exc)}


async def create_scope(
    name: str,
    allow: list[str] | None = None,
    deny: list[str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Create a new scope.

    Args:
        name:   Scope name.
        allow:  Allowlist of glob patterns.
        deny:   Denylist of glob patterns.
        client: Optional pre-built Caido Client instance.

    Returns:
        Created scope dict, or dict with ``error`` key on failure.
    """
    try:
        from caido_sdk_client.types import CreateScopeOptions

        c = client or await get_client()
        opts = CreateScopeOptions(
            name=name,
            allowlist=allow or [],
            denylist=deny or [],
        )
        scope = await c.scope.create(opts)
        return _scope_to_dict(scope)
    except Exception as exc:
        return {"error": str(exc)}


async def delete_scope(
    scope_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Delete a scope by ID.

    Args:
        scope_id: The scope ID to delete.
        client:   Optional pre-built Caido Client instance.

    Returns:
        Dict with ``deleted`` key, or ``error`` on failure.
    """
    try:
        c = client or await get_client()
        await c.scope.delete(scope_id)
        return {"deleted": scope_id}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Filter (preset) operations
# ---------------------------------------------------------------------------

async def filters(
    limit: int = 50,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """List filter presets.

    Args:
        limit:  Maximum number of filters to return (default 50).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of filter preset dicts.
    """
    try:
        c = client or await get_client()
        items = await c.filter.list()
        return [_filter_to_dict(f) for f in items[:limit]]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_filter(
    name: str,
    httpql: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Create a new filter preset.

    Args:
        name:   Filter preset name.
        httpql: The HTTPQL filter clause.
        client: Optional pre-built Caido Client instance.

    Returns:
        Created filter preset dict, or dict with ``error`` on failure.
    """
    try:
        from caido_sdk_client.types import CreateFilterPresetOptions

        c = client or await get_client()
        opts = CreateFilterPresetOptions(
            name=name,
            alias=name,
            clause=httpql,
        )
        fp = await c.filter.create(opts)
        return _filter_to_dict(fp)
    except Exception as exc:
        return {"error": str(exc)}


async def delete_filter(
    filter_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Delete a filter preset by ID.

    Args:
        filter_id: The filter preset ID to delete.
        client:    Optional pre-built Caido Client instance.

    Returns:
        Dict with ``deleted`` key, or ``error`` on failure.
    """
    try:
        c = client or await get_client()
        await c.filter.delete(filter_id)
        return {"deleted": filter_id}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Environment operations
# ---------------------------------------------------------------------------

async def environments(
    limit: int = 50,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """List environments.

    Args:
        limit:  Maximum number of environments to return (default 50).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of environment dicts.
    """
    try:
        c = client or await get_client()
        items = await c.environment.list()
        return [_environment_to_dict(e) for e in items[:limit]]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_environment(
    name: str,
    variables: dict[str, str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Create a new environment.

    Args:
        name:      Environment name.
        variables: Optional dict of variable name → value pairs.
        client:    Optional pre-built Caido Client instance.

    Returns:
        Created environment dict, or dict with ``error`` on failure.
    """
    try:
        from caido_sdk_client.graphql.__generated__.schema import (
            EnvironmentVariableKind,
        )
        from caido_sdk_client.types import (
            CreateEnvironmentOptions,
            EnvironmentVariable,
        )

        c = client or await get_client()
        env_vars = [
            EnvironmentVariable(name=k, value=v, kind=EnvironmentVariableKind.STRING)
            for k, v in (variables or {}).items()
        ]
        opts = CreateEnvironmentOptions(name=name, variables=env_vars)
        env = await c.environment.create(opts)
        return _environment_to_dict(env)
    except Exception as exc:
        return {"error": str(exc)}


async def delete_environment(
    env_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Delete an environment by ID.

    Args:
        env_id: The environment ID to delete.
        client: Optional pre-built Caido Client instance.

    Returns:
        Dict with ``deleted`` key, or ``error`` on failure.
    """
    try:
        c = client or await get_client()
        await c.environment.delete(env_id)
        return {"deleted": env_id}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Project operations
# ---------------------------------------------------------------------------

async def projects(
    limit: int = 50,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """List projects.

    Args:
        limit:  Maximum number of projects to return (default 50).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of project dicts.
    """
    try:
        c = client or await get_client()
        items = await c.project.list()
        return [_project_to_dict(p) for p in items[:limit]]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_project(
    name: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Create a new project.

    Args:
        name:   Project name.
        client: Optional pre-built Caido Client instance.

    Returns:
        Created project dict, or dict with ``error`` on failure.
    """
    try:
        from caido_sdk_client.types import CreateProjectOptions

        c = client or await get_client()
        opts = CreateProjectOptions(name=name, temporary=False)
        proj = await c.project.create(opts)
        return _project_to_dict(proj)
    except Exception as exc:
        return {"error": str(exc)}


async def delete_project(
    project_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Delete a project by ID.

    Args:
        project_id: The project ID to delete.
        client:     Optional pre-built Caido Client instance.

    Returns:
        Dict with ``deleted`` key, or ``error`` on failure.
    """
    try:
        c = client or await get_client()
        await c.project.delete(project_id)
        return {"deleted": project_id}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Hosted file operations
# ---------------------------------------------------------------------------

async def hosted_files(
    limit: int = 50,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """List hosted files.

    Args:
        limit:  Maximum number of hosted files to return (default 50).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of hosted file dicts.
    """
    try:
        c = client or await get_client()
        items = await c.hosted_file.list()
        return [_hosted_file_to_dict(hf) for hf in items[:limit]]
    except Exception as exc:
        return [{"error": str(exc)}]


# ---------------------------------------------------------------------------
# Task operations
# ---------------------------------------------------------------------------

async def tasks(
    limit: int = 20,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """List tasks.

    Args:
        limit:  Maximum number of tasks to return (default 20).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of task dicts.
    """
    try:
        c = client or await get_client()
        items = await c.task.list()
        return [_task_to_dict(t) for t in items[:limit]]
    except Exception as exc:
        return [{"error": str(exc)}]


async def cancel_task(
    task_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Cancel a task by ID.

    Args:
        task_id: The task ID to cancel.
        client:  Optional pre-built Caido Client instance.

    Returns:
        Dict with ``cancelled`` key, or ``error`` on failure.
    """
    try:
        c = client or await get_client()
        await c.task.cancel(task_id)
        return {"cancelled": task_id}
    except Exception as exc:
        return {"error": str(exc)}
