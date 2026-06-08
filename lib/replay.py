"""Replay operations for the Caido CLI.

Wraps the Caido Python SDK ReplaySDK, converting async SDK objects into
plain dicts suitable for CLI output.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client import get_client  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry_to_dict(entry: object) -> dict:
    """Convert a ReplayEntry SDK object to a plain dict."""
    d: dict = {
        "id": str(entry.id) if getattr(entry, "id", None) else None,
        "sessionId": str(entry.session_id) if getattr(entry, "session_id", None) else None,
        "createdAt": str(entry.created_at) if getattr(entry, "created_at", None) else None,
        "error": entry.error,
    }

    # Connection info
    conn = getattr(entry, "connection", None)
    if conn:
        d["connection"] = {
            "host": conn.host,
            "port": conn.port,
            "isTls": conn.is_tls,
            "sni": conn.sni,
        }

    # Request
    req = getattr(entry, "request", None)
    if req:
        req_dict: dict = {
            "id": str(req.id) if getattr(req, "id", None) else None,
            "host": req.host,
            "port": req.port,
            "method": req.method,
            "path": req.path,
            "query": req.query,
            "isTls": req.is_tls,
        }
        if getattr(req, "raw", None):
            try:
                req_dict["raw"] = req.raw.decode("utf-8", errors="replace")
            except Exception:
                req_dict["raw"] = repr(req.raw)
        d["request"] = req_dict

    # Response
    resp = getattr(entry, "response", None)
    if resp:
        resp_dict: dict = {
            "id": str(resp.id) if getattr(resp, "id", None) else None,
            "statusCode": resp.status_code,
            "roundtripTime": resp.roundtrip_time,
            "length": resp.length,
        }
        if getattr(resp, "raw", None):
            try:
                resp_dict["raw"] = resp.raw.decode("utf-8", errors="replace")
            except Exception:
                resp_dict["raw"] = repr(resp.raw)
        d["response"] = resp_dict

    # Raw combined request+response bytes
    if getattr(entry, "raw", None):
        try:
            d["raw"] = entry.raw.decode("utf-8", errors="replace")
        except Exception:
            d["raw"] = repr(entry.raw)

    return d


def _session_to_dict(session: object) -> dict:
    """Convert a ReplaySession SDK object to a plain dict."""
    return {
        "id": str(session.id),
        "name": session.name,
        "collectionId": str(session.collection_id) if getattr(session, "collection_id", None) else None,
        "activeEntryId": str(session.active_entry_id) if getattr(session, "active_entry_id", None) else None,
    }


def _collection_to_dict(collection: object) -> dict:
    """Convert a ReplaySessionCollection SDK object to a plain dict."""
    return {
        "id": str(collection.id),
        "name": collection.name,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def replay(request_id: str, client=None) -> dict:
    """Send a request through replay by its request ID.

    Creates a replay session from the existing request, sends it, waits for
    the task to finish, and returns the result as a plain dict.

    Args:
        request_id: The ID of an existing request to replay.
        client:     Optional pre-built Caido Client instance.

    Returns:
        Dict with keys: ``taskId``, ``status``, ``entry`` (or ``error``).
    """
    try:
        c = client or await get_client()
        from caido_sdk_client import CreateReplaySessionFromId, CreateReplaySessionOptions

        # Create a session seeded with the existing request
        session = await c.replay.sessions.create(
            CreateReplaySessionOptions(
                request_source=CreateReplaySessionFromId(id=request_id),
            )
        )

        # Retrieve the entry that was created from the request source.
        # The session's first entry holds the replay result after send.
        entries_conn = await session.entries().first(1)
        if not entries_conn.edges:
            return {"error": "No entries found in replay session after creation"}

        entry = entries_conn.edges[0].node

        # The entry was loaded; return it directly (the session is already
        # populated from the source request).  We don't need to call send()
        # separately – the entry already has the response once the task
        # finishes.
        result: dict = {
            "status": "DONE",
            "entry": _entry_to_dict(entry),
        }

        # Clean up the ephemeral session
        try:
            await c.replay.sessions.delete([session.id])
        except Exception:
            pass

        return result
    except Exception as exc:
        return {"error": str(exc)}


async def send_raw(
    raw_request: str,
    host: str,
    port: int = 443,
    tls: bool = True,
    sni: str | None = None,
    client=None,
) -> dict:
    """Send a raw HTTP request through replay.

    Args:
        raw_request: The full raw HTTP request as a string.
        host:        Target host.
        port:        Target port (default 443).
        tls:         Whether to use TLS (default True).
        sni:         Server Name Indication value (optional).
        client:      Optional pre-built Caido Client instance.

    Returns:
        Dict with keys: ``status``, ``entry`` (or ``error``).
    """
    try:
        c = client or await get_client()
        from caido_sdk_client import (
            ConnectionInfoInput,
            CreateReplaySessionFromRaw,
            CreateReplaySessionOptions,
            ReplaySendOptions,
        )

        connection = ConnectionInfoInput(
            host=host,
            port=port,
            is_tls=tls,
            sni=sni or "",
        )

        # Create a session from the raw request
        session = await c.replay.sessions.create(
            CreateReplaySessionOptions(
                request_source=CreateReplaySessionFromRaw(
                    raw=raw_request,
                    connection=connection,
                ),
            )
        )

        # Send through replay and wait for completion
        send_result = await c.replay.send(
            session.id,
            ReplaySendOptions(
                raw=raw_request.encode() if isinstance(raw_request, str) else raw_request,
                connection=connection,
            ),
        )

        result: dict = {
            "status": str(send_result.status),
            "entry": _entry_to_dict(send_result.entry),
        }
        if send_result.error:
            result["error"] = send_result.error

        # Clean up
        try:
            await c.replay.sessions.delete([session.id])
        except Exception:
            pass

        return result
    except Exception as exc:
        return {"error": str(exc)}


async def edit(
    entry_id: str,
    raw_request: str | None = None,
    host: str | None = None,
    port: int | None = None,
    tls: bool | None = None,
    client=None,
) -> dict:
    """Edit and resend a replay entry.

    Fetches the existing entry, optionally overrides fields, then sends the
    modified request through replay.

    Args:
        entry_id:    ID of the existing replay entry.
        raw_request: Replacement raw HTTP request (optional; uses original if omitted).
        host:        Override target host (optional).
        port:        Override target port (optional).
        tls:         Override TLS flag (optional).
        client:      Optional pre-built Caido Client instance.

    Returns:
        Dict with keys: ``status``, ``entry`` (or ``error``).
    """
    try:
        c = client or await get_client()

        # Fetch the existing entry
        entry = await c.replay.entries.get(entry_id)
        if entry is None:
            return {"error": f"Entry {entry_id!r} not found"}

        # Resolve fields (use provided values or fall back to the original)
        conn = entry.connection
        resolved_host = host or conn.host
        resolved_port = port if port is not None else conn.port
        resolved_tls = tls if tls is not None else conn.is_tls
        resolved_sni = conn.sni

        resolved_raw = raw_request
        if resolved_raw is None and entry.raw:
            resolved_raw = entry.raw.decode("utf-8", errors="replace")
        if resolved_raw is None and entry.request and entry.request.raw:
            resolved_raw = entry.request.raw.decode("utf-8", errors="replace")
        if resolved_raw is None:
            return {"error": "No raw request available on the entry to edit"}

        # Create a new session and send the modified request
        from caido_sdk_client import (
            ConnectionInfoInput,
            CreateReplaySessionFromRaw,
            CreateReplaySessionOptions,
            ReplaySendOptions,
        )

        connection = ConnectionInfoInput(
            host=resolved_host,
            port=resolved_port,
            is_tls=resolved_tls,
            sni=resolved_sni,
        )

        session = await c.replay.sessions.create(
            CreateReplaySessionOptions(
                request_source=CreateReplaySessionFromRaw(
                    raw=resolved_raw,
                    connection=connection,
                ),
            )
        )

        send_result = await c.replay.send(
            session.id,
            ReplaySendOptions(
                raw=resolved_raw.encode() if isinstance(resolved_raw, str) else resolved_raw,
                connection=connection,
            ),
        )

        result: dict = {
            "status": str(send_result.status),
            "entry": _entry_to_dict(send_result.entry),
        }
        if send_result.error:
            result["error"] = send_result.error

        # Clean up
        try:
            await c.replay.sessions.delete([session.id])
        except Exception:
            pass

        return result
    except Exception as exc:
        return {"error": str(exc)}


async def sessions(limit: int = 50, client=None) -> list:
    """List replay sessions.

    Args:
        limit:  Maximum number of sessions to return (default 50).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of dicts, each with keys: ``id``, ``name``, ``collectionId``,
        ``activeEntryId``.
    """
    try:
        c = client or await get_client()
        conn = await c.replay.sessions.list().first(limit)
        return [_session_to_dict(edge.node) for edge in conn.edges]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_session(
    name: str | None = None,
    collection_id: str | None = None,
    client=None,
) -> dict:
    """Create a new replay session.

    Args:
        name:          Optional session name.
        collection_id: Optional collection to place the session in.
        client:        Optional pre-built Caido Client instance.

    Returns:
        Dict with keys: ``id``, ``name``, ``collectionId``,
        ``activeEntryId`` (or ``error``).
    """
    try:
        c = client or await get_client()
        from caido_sdk_client import CreateReplaySessionOptions

        opts = CreateReplaySessionOptions(collection_id=collection_id)
        session = await c.replay.sessions.create(opts)

        result = _session_to_dict(session)
        if name:
            session = await c.replay.sessions.rename(session.id, name)
            result = _session_to_dict(session)

        return result
    except Exception as exc:
        return {"error": str(exc)}


async def rename_session(session_id: str, name: str, client=None) -> dict:
    """Rename a replay session.

    Args:
        session_id: ID of the session to rename.
        name:       New name for the session.
        client:     Optional pre-built Caido Client instance.

    Returns:
        Dict with updated session info (or ``error``).
    """
    try:
        c = client or await get_client()
        session = await c.replay.sessions.rename(session_id, name)
        return _session_to_dict(session)
    except Exception as exc:
        return {"error": str(exc)}


async def delete_sessions(ids: list[str], client=None) -> dict:
    """Delete replay sessions by ID.

    Args:
        ids:    List of session IDs to delete.
        client: Optional pre-built Caido Client instance.

    Returns:
        Dict with ``deleted`` count or ``error``.
    """
    try:
        c = client or await get_client()
        await c.replay.sessions.delete(ids)
        return {"deleted": len(ids), "ids": ids}
    except Exception as exc:
        return {"error": str(exc)}


async def session_entries(session_id: str, limit: int = 50, client=None) -> list:
    """List entries in a replay session.

    Args:
        session_id: ID of the replay session.
        limit:      Maximum number of entries to return (default 50).
        client:     Optional pre-built Caido Client instance.

    Returns:
        List of entry dicts.
    """
    try:
        c = client or await get_client()
        session = await c.replay.sessions.get(session_id)
        if session is None:
            return [{"error": f"Session {session_id!r} not found"}]
        conn = await session.entries().first(limit)
        return [_entry_to_dict(edge.node) for edge in conn.edges]
    except Exception as exc:
        return [{"error": str(exc)}]


async def collections(limit: int = 50, client=None) -> list:
    """List replay collections.

    Args:
        limit:  Maximum number of collections to return (default 50).
        client: Optional pre-built Caido Client instance.

    Returns:
        List of dicts with keys: ``id``, ``name``.
    """
    try:
        c = client or await get_client()
        conn = await c.replay.collections.list().first(limit)
        return [_collection_to_dict(edge.node) for edge in conn.edges]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_collection(name: str, client=None) -> dict:
    """Create a replay collection.

    Args:
        name:   Name for the new collection.
        client: Optional pre-built Caido Client instance.

    Returns:
        Dict with keys: ``id``, ``name`` (or ``error``).
    """
    try:
        c = client or await get_client()
        from caido_sdk_client import CreateReplaySessionCollectionOptions

        collection = await c.replay.collections.create(
            CreateReplaySessionCollectionOptions(name=name),
        )
        return _collection_to_dict(collection)
    except Exception as exc:
        return {"error": str(exc)}
