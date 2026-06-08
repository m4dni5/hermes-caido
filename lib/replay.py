"""Replay operations for the Caido CLI.

Uses raw GraphQL queries via the client module — no SDK dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client import graphql  # noqa: E402

# ---------------------------------------------------------------------------
# GraphQL operations
# ---------------------------------------------------------------------------

_SEND_REPLAY = """mutation SendReplay($requestId: ID!) {
  sendReplay(requestId: $requestId) {
    ... on SendReplaySuccess {
      requestEntry { id }
    }
    ... on SendReplayError {
      message
    }
  }
}"""

_SEND_RAW_REQUEST = """mutation SendRawRequest($input: RawRequestInput!) {
  sendRawRequest(input: $input) {
    ... on SendRawRequestSuccess {
      requestEntry {
        id
        host
        method
        path
        response { code }
      }
    }
    ... on SendRawRequestError {
      message
    }
  }
}"""

_REPLAY_SESSIONS = """query ReplaySessions {
  replay {
    sessions {
      id
      name
      activeEntry { id }
    }
  }
}"""

_CREATE_REPLAY_SESSION = """mutation CreateReplaySession($input: CreateReplaySessionInput!) {
  createReplaySession(input: $input) {
    ... on CreateReplaySessionSuccess {
      session { id name }
    }
    ... on CreateReplaySessionError {
      message
    }
  }
}"""

_RENAME_REPLAY_SESSION = """mutation RenameReplaySession($input: RenameReplaySessionInput!) {
  renameReplaySession(input: $input) {
    ... on RenameReplaySessionSuccess {
      session { id name }
    }
    ... on RenameReplaySessionError {
      message
    }
  }
}"""

_DELETE_REPLAY_SESSIONS = """mutation DeleteReplaySessions($input: DeleteReplaySessionsInput!) {
  deleteReplaySessions(input: $input) {
    ... on DeleteReplaySessionsSuccess {
      deletedIds
    }
    ... on DeleteReplaySessionsError {
      message
    }
  }
}"""

_REPLAY_SESSION_ENTRIES = """query ReplaySessionEntries($sessionId: ID!) {
  replay {
    session(id: $sessionId) {
      entries {
        id
        requestEntry {
          id
          host
          method
          path
          response { code }
        }
      }
    }
  }
}"""

_REPLAY_COLLECTIONS = """query ReplayCollections {
  replay {
    collections {
      id
      name
    }
  }
}"""

_CREATE_REPLAY_COLLECTION = """mutation CreateReplayCollection($input: CreateReplayCollectionInput!) {
  createReplayCollection(input: $input) {
    ... on CreateReplayCollectionSuccess {
      collection { id name }
    }
    ... on CreateReplayCollectionError {
      message
    }
  }
}"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def replay(request_id: str, client=None) -> dict:
    """Send a request through replay by its request ID.

    Uses the ``sendReplay`` mutation which dispatches an existing request
    through the replay pipeline.

    Args:
        request_id: The ID of an existing request to replay.
        client:     Unused (kept for signature compat); calls ``graphql``
                    directly.

    Returns:
        Dict with the resulting request entry info, or ``error``.
    """
    try:
        data = await graphql(_SEND_REPLAY, {"requestId": request_id})
        result = data.get("sendReplay", {})
        if "message" in result:
            return {"error": result["message"]}
        entry = result.get("requestEntry", {})
        return {"status": "DONE", "entry": entry}
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
        sni:         Server Name Indication value (optional, unused in
                     current GraphQL schema).
        client:      Unused (kept for signature compat).

    Returns:
        Dict with ``status``, ``entry`` (or ``error``).
    """
    try:
        input_vars: dict = {
            "rawRequest": raw_request,
            "host": host,
            "port": port,
            "tls": tls,
        }
        data = await graphql(_SEND_RAW_REQUEST, {"input": input_vars})
        result = data.get("sendRawRequest", {})
        if "message" in result:
            return {"error": result["message"]}
        entry = result.get("requestEntry", {})
        return {"status": "DONE", "entry": entry}
    except Exception as exc:
        return {"error": str(exc)}


async def sessions(limit: int = 50, client=None) -> list:
    """List replay sessions.

    Args:
        limit:  Maximum number of sessions to return (default 50).
        client: Unused (kept for signature compat).

    Returns:
        List of dicts, each with keys: ``id``, ``name``, ``activeEntryId``.
    """
    try:
        data = await graphql(_REPLAY_SESSIONS)
        raw = data.get("replay", {}).get("sessions", [])
        out = []
        for s in raw[:limit]:
            out.append({
                "id": s.get("id"),
                "name": s.get("name"),
                "activeEntryId": (s.get("activeEntry") or {}).get("id"),
            })
        return out
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
        client:        Unused (kept for signature compat).

    Returns:
        Dict with keys: ``id``, ``name`` (or ``error``).
    """
    try:
        input_vars: dict = {}
        if name:
            input_vars["name"] = name
        if collection_id:
            input_vars["collectionId"] = collection_id

        data = await graphql(_CREATE_REPLAY_SESSION, {"input": input_vars})
        result = data.get("createReplaySession", {})
        if "message" in result:
            return {"error": result["message"]}
        session = result.get("session", {})
        return {"id": session.get("id"), "name": session.get("name")}
    except Exception as exc:
        return {"error": str(exc)}


async def rename_session(session_id: str, name: str, client=None) -> dict:
    """Rename a replay session.

    Args:
        session_id: ID of the session to rename.
        name:       New name for the session.
        client:     Unused (kept for signature compat).

    Returns:
        Dict with updated session info (or ``error``).
    """
    try:
        data = await graphql(
            _RENAME_REPLAY_SESSION,
            {"input": {"id": session_id, "name": name}},
        )
        result = data.get("renameReplaySession", {})
        if "message" in result:
            return {"error": result["message"]}
        session = result.get("session", {})
        return {"id": session.get("id"), "name": session.get("name")}
    except Exception as exc:
        return {"error": str(exc)}


async def delete_sessions(ids: list[str], client=None) -> dict:
    """Delete replay sessions by ID.

    Args:
        ids:    List of session IDs to delete.
        client: Unused (kept for signature compat).

    Returns:
        Dict with ``deletedIds`` or ``error``.
    """
    try:
        data = await graphql(
            _DELETE_REPLAY_SESSIONS,
            {"input": {"ids": ids}},
        )
        result = data.get("deleteReplaySessions", {})
        if "message" in result:
            return {"error": result["message"]}
        return {"deleted": len(ids), "ids": result.get("deletedIds", ids)}
    except Exception as exc:
        return {"error": str(exc)}


async def session_entries(session_id: str, limit: int = 50, client=None) -> list:
    """List entries in a replay session.

    Args:
        session_id: ID of the replay session.
        limit:      Maximum number of entries to return (default 50).
        client:     Unused (kept for signature compat).

    Returns:
        List of entry dicts.
    """
    try:
        data = await graphql(_REPLAY_SESSION_ENTRIES, {"sessionId": session_id})
        session = data.get("replay", {}).get("session", {})
        if session is None:
            return [{"error": f"Session {session_id!r} not found"}]
        entries = session.get("entries", [])
        out = []
        for e in entries[:limit]:
            req = e.get("requestEntry") or {}
            out.append({
                "id": e.get("id"),
                "requestEntry": {
                    "id": req.get("id"),
                    "host": req.get("host"),
                    "method": req.get("method"),
                    "path": req.get("path"),
                    "responseCode": (req.get("response") or {}).get("code"),
                },
            })
        return out
    except Exception as exc:
        return [{"error": str(exc)}]


async def collections(limit: int = 50, client=None) -> list:
    """List replay collections.

    Args:
        limit:  Maximum number of collections to return (default 50).
        client: Unused (kept for signature compat).

    Returns:
        List of dicts with keys: ``id``, ``name``.
    """
    try:
        data = await graphql(_REPLAY_COLLECTIONS)
        raw = data.get("replay", {}).get("collections", [])
        return [{"id": c.get("id"), "name": c.get("name")} for c in raw[:limit]]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_collection(name: str, client=None) -> dict:
    """Create a replay collection.

    Args:
        name:   Name for the new collection.
        client: Unused (kept for signature compat).

    Returns:
        Dict with keys: ``id``, ``name`` (or ``error``).
    """
    try:
        data = await graphql(
            _CREATE_REPLAY_COLLECTION,
            {"input": {"name": name}},
        )
        result = data.get("createReplayCollection", {})
        if "message" in result:
            return {"error": result["message"]}
        collection = result.get("collection", {})
        return {"id": collection.get("id"), "name": collection.get("name")}
    except Exception as exc:
        return {"error": str(exc)}
