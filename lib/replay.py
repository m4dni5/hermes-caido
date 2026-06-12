"""Caido replay operations — sync wrappers.

Usage:
    import replay
    result = replay.replay(request_id="123")
    result = replay.replay_with_edit(request_id="123", path="/admin")
"""

from __future__ import annotations
from sync import sync_run
from graphql.replay import (
    replay as _replay,
    replay_with_edit as _replay_with_edit,
    sessions as _sessions,
    get_session as _get_session,
    get_session_entries as _get_session_entries,
    get_entry as _get_entry,
    create_session as _create_session,
    rename_session as _rename_session,
    delete_sessions as _delete_sessions,
    move_session as _move_session,
    update_entry_draft as _update_entry_draft,
    clear_entry_draft as _clear_entry_draft,
    start_replay_task as _start_replay_task,
    collections as _collections,
    create_collection as _create_collection,
)


def replay(request_id: str) -> dict:
    """Replay a request by ID."""
    return sync_run(_replay, request_id)


def replay_with_edit(
    request_id: str,
    path: str | None = None,
    method: str | None = None,
    headers: list[tuple[str, str]] | None = None,
    body: str | None = None,
    session_name: str | None = None,
) -> dict:
    """Edit a request and replay it."""
    return sync_run(
        _replay_with_edit,
        request_id=request_id,
        path=path,
        method=method,
        headers=headers,
        body=body,
        session_name=session_name,
    )


def sessions(limit: int = 50) -> list:
    """List replay sessions."""
    return sync_run(_sessions, limit)


def get_session(session_id: str) -> dict:
    """Get a replay session with entries."""
    return sync_run(_get_session, session_id)


def get_session_entries(session_id: str) -> list:
    """Get entries from a replay session."""
    return sync_run(_get_session_entries, session_id)


def get_entry(entry_id: str) -> dict:
    """Get a specific replay entry."""
    return sync_run(_get_entry, entry_id)


def create_session(
    name: str | None = None,
    request_id: str | None = None,
    collection_id: str | None = None,
) -> dict:
    """Create a replay session."""
    return sync_run(_create_session, name=name, request_id=request_id, collection_id=collection_id)


def rename_session(session_id: str, name: str) -> dict:
    """Rename a replay session."""
    return sync_run(_rename_session, session_id, name)


def delete_sessions(ids: list[str]) -> dict:
    """Delete replay sessions."""
    return sync_run(_delete_sessions, ids)


def move_session(session_id: str, collection_id: str) -> dict:
    """Move a session to a collection."""
    return sync_run(_move_session, session_id, collection_id)


def update_entry_draft(
    entry_id: str,
    raw: str,
    host: str,
    port: int = 443,
    is_tls: bool = True,
) -> dict:
    """Update a replay entry's draft."""
    return sync_run(_update_entry_draft, entry_id=entry_id, raw=raw, host=host, port=port, is_tls=is_tls)


def clear_entry_draft(entry_id: str) -> dict:
    """Clear a replay entry's draft."""
    return sync_run(_clear_entry_draft, entry_id)


def start_replay_task(session_id: str) -> dict:
    """Start a replay task."""
    return sync_run(_start_replay_task, session_id)


def collections(limit: int = 50) -> list:
    """List replay collections."""
    return sync_run(_collections, limit)


def create_collection(name: str) -> dict:
    """Create a replay collection."""
    return sync_run(_create_collection, name)
