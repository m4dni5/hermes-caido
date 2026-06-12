"""Caido automate operations — sync wrappers.

Usage:
    import automate
    sessions = automate.sessions()
    result = automate.create_session(request_id="123")
"""

from __future__ import annotations
from sync import sync_run
from graphql.automate import (
    sessions as _sessions,
    get_session as _get_session,
    create_session as _create_session,
    rename_session as _rename_session,
    update_session as _update_session,
    delete_session as _delete_session,
    duplicate_session as _duplicate_session,
    start_task as _start_task,
    list_tasks as _list_tasks,
    cancel_task as _cancel_task,
    pause_task as _pause_task,
    resume_task as _resume_task,
)


def sessions(limit: int = 50) -> list:
    """List automate sessions."""
    return sync_run(_sessions, limit)


def get_session(session_id: str) -> dict:
    """Get an automate session with entries and settings."""
    return sync_run(_get_session, session_id)


def create_session(request_id: str | None = None) -> dict:
    """Create an automate session, optionally from a proxy request ID."""
    return sync_run(_create_session, request_id=request_id)


def rename_session(session_id: str, name: str) -> dict:
    """Rename an automate session."""
    return sync_run(_rename_session, session_id, name)


def update_session(
    session_id: str,
    raw: str | None = None,
    connection: dict | None = None,
    settings: dict | None = None,
) -> dict:
    """Update a session's raw request, connection, or settings."""
    return sync_run(_update_session, session_id, raw=raw, connection=connection, settings=settings)


def delete_session(session_id: str) -> dict:
    """Delete an automate session."""
    return sync_run(_delete_session, session_id)


def duplicate_session(session_id: str) -> dict:
    """Duplicate an automate session."""
    return sync_run(_duplicate_session, session_id)


def start_task(session_id: str) -> dict:
    """Start an automate task from a session."""
    return sync_run(_start_task, session_id)


def list_tasks(limit: int = 50) -> list:
    """List automate tasks."""
    return sync_run(_list_tasks, limit)


def cancel_task(task_id: str) -> dict:
    """Cancel an automate task."""
    return sync_run(_cancel_task, task_id)


def pause_task(task_id: str) -> dict:
    """Pause a running automate task."""
    return sync_run(_pause_task, task_id)


def resume_task(task_id: str) -> dict:
    """Resume a paused automate task."""
    return sync_run(_resume_task, task_id)
