"""Replay operations for the Caido CLI.

Uses raw GraphQL queries via the client module — no SDK dependency.
Matches the real Caido GraphQL schema (replay sessions, collections, tasks).
"""

from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client import graphql  # noqa: E402
from http_requests import get as get_request  # noqa: E402

# ---------------------------------------------------------------------------
# GraphQL fragments
# ---------------------------------------------------------------------------

_FRAGMENT_REPLAY_SESSION_META = """fragment ReplaySessionMeta on ReplaySession {
  id
  name
}"""

_FRAGMENT_REPLAY_SESSION_COLLECTION_META = """fragment ReplaySessionCollectionMeta on ReplaySessionCollection {
  id
  name
}"""

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

_REPLAY_SESSIONS = f"""{_FRAGMENT_REPLAY_SESSION_META}

query ReplaySessions($first: Int, $after: String, $last: Int, $before: String) {{
  replaySessions(first: $first, after: $after, last: $last, before: $before) {{
    edges {{
      cursor
      node {{ ...ReplaySessionMeta }}
    }}
    pageInfo {{ hasNextPage hasPreviousPage startCursor endCursor }}
  }}
}}"""

_REPLAY_SESSION_COLLECTIONS = f"""{_FRAGMENT_REPLAY_SESSION_COLLECTION_META}

query ReplaySessionCollections($first: Int, $after: String, $last: Int, $before: String) {{
  replaySessionCollections(first: $first, after: $after, last: $last, before: $before) {{
    edges {{
      cursor
      node {{ ...ReplaySessionCollectionMeta }}
    }}
    pageInfo {{ hasNextPage hasPreviousPage startCursor endCursor }}
  }}
}}"""

# ---------------------------------------------------------------------------
# GraphQL mutations
# ---------------------------------------------------------------------------

_CREATE_REPLAY_SESSION = """mutation CreateReplaySession($input: CreateReplaySessionInput!) {
  createReplaySession(input: $input) {
    session { id name }
  }
}"""

_RENAME_REPLAY_SESSION = """mutation RenameReplaySession($id: ID!, $name: String!) {
  renameReplaySession(id: $id, name: $name) {
    session { id name }
  }
}"""

_DELETE_REPLAY_SESSIONS = """mutation DeleteReplaySessions($ids: [ID!]!) {
  deleteReplaySessions(ids: $ids) {
    deletedIds
  }
}"""

_CREATE_REPLAY_SESSION_COLLECTION = """mutation CreateReplaySessionCollection($input: CreateReplaySessionCollectionInput!) {
  createReplaySessionCollection(input: $input) {
    collection { id name }
  }
}"""

_START_REPLAY_TASK = """mutation StartReplayTask($sessionId: ID!, $input: StartReplayTaskInput!) {
  startReplayTask(sessionId: $sessionId, input: $input) {
    error {
      __typename
      ... on CloudUserError { code }
      ... on OtherUserError { code }
    }
    task { id }
  }
}"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def replay(request_id: str, client=None) -> dict:
    """Replay an existing request by its request ID.

    Composite operation: fetches the request, extracts raw HTTP bytes,
    then sends via the replay system.

    Args:
        request_id: The ID of an existing request to replay.
        client:     Unused (kept for signature compat).

    Returns:
        Dict with ``status``, ``sessionId``, ``taskId`` (or ``error``).
    """
    try:
        # Step 1: Fetch the request with raw bytes
        req = await get_request(request_id=request_id)
        if "error" in req:
            return req

        raw = req.get("requestRaw")
        if not raw:
            return {
                "error": f"Request {request_id!r} has no raw bytes. "
                "Cannot replay without raw HTTP content."
            }

        host = req.get("host", "")
        port = req.get("port", 443)
        is_tls = req.get("isTls", True)

        # Step 2: Send via replay system
        return await send_raw(
            raw_request=raw,
            host=host,
            port=port,
            tls=is_tls,
        )
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
    """Send a raw HTTP request through the Caido replay system.

    Creates a replay session, then starts a replay task with the raw
    request content.

    Args:
        raw_request: The full raw HTTP request as a string.
        host:        Target host.
        port:        Target port (default 443).
        tls:         Whether to use TLS (default True).
        sni:         Server Name Indication value (optional).
        client:      Unused (kept for signature compat).

    Returns:
        Dict with ``sessionId``, ``taskId`` (or ``error``).
    """
    try:
        # Step 1: Create a replay session for this request
        session_result = await create_session(name=f"replay-{host}")
        if "error" in session_result:
            return session_result

        session_id = session_result["id"]

        # Step 2: Start a replay task with the raw request
        task_input: dict = {
            "requestContent": raw_request,
            "host": host,
            "port": port,
            "isTls": tls,
        }
        if sni is not None:
            task_input["sni"] = sni

        data = await graphql(_START_REPLAY_TASK, {
            "sessionId": session_id,
            "input": task_input,
        })

        result = data.get("startReplayTask", {})
        error = result.get("error")
        if error:
            return {"error": error.get("message", str(error))}

        task = result.get("task", {})
        return {
            "status": "DONE",
            "sessionId": session_id,
            "taskId": task.get("id"),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def sessions(limit: int = 50, client=None) -> list:
    """List replay sessions.

    Args:
        limit:  Maximum number of sessions to return (default 50).
        client: Unused (kept for signature compat).

    Returns:
        List of dicts, each with keys: ``id``, ``name``.
    """
    try:
        data = await graphql(_REPLAY_SESSIONS, {"first": limit})
        connection = data.get("replaySessions", {})
        edges = connection.get("edges", [])
        return [
            {"id": s.get("id"), "name": s.get("name")}
            for edge in edges
            if (s := edge.get("node"))
        ]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_session(
    name: str | None = None,
    collection_id: str | None = None,
    client=None,
) -> dict:
    """Create a new replay session.

    Args:
        name:          Optional session name (set via rename after creation).
        collection_id: Optional collection to place the session in.
        client:        Unused (kept for signature compat).

    Returns:
        Dict with keys: ``id``, ``name`` (or ``error``).
    """
    try:
        input_vars: dict = {"kind": "HTTP"}
        if collection_id:
            input_vars["collectionId"] = collection_id

        data = await graphql(_CREATE_REPLAY_SESSION, {"input": input_vars})
        result = data.get("createReplaySession", {})
        session = result.get("session", {})
        if not session:
            return {"error": "Failed to create session (no session in response)"}
        session_id = session.get("id")

        # Rename if name provided (createReplaySession has no name field)
        if name and session_id:
            await rename_session(session_id, name)

        return {"id": session_id, "name": name or session.get("name", "")}
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
            {"id": session_id, "name": name},
        )
        result = data.get("renameReplaySession", {})
        session = result.get("session", {})
        if not session:
            return {"error": "Failed to rename session (no session in response)"}
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
            {"ids": ids},
        )
        result = data.get("deleteReplaySessions", {})
        deleted_ids = result.get("deletedIds", [])
        return {"deleted": len(deleted_ids), "ids": deleted_ids}
    except Exception as exc:
        return {"error": str(exc)}


async def collections(limit: int = 50, client=None) -> list:
    """List replay session collections.

    Args:
        limit:  Maximum number of collections to return (default 50).
        client: Unused (kept for signature compat).

    Returns:
        List of dicts with keys: ``id``, ``name``.
    """
    try:
        data = await graphql(_REPLAY_SESSION_COLLECTIONS, {"first": limit})
        connection = data.get("replaySessionCollections", {})
        edges = connection.get("edges", [])
        return [
            {"id": e.get("node", {}).get("id"), "name": e.get("node", {}).get("name")}
            for e in edges
        ]
    except Exception as exc:
        return [{"error": str(exc)}]


async def create_collection(name: str, client=None) -> dict:
    """Create a replay session collection.

    Args:
        name:   Name for the new collection.
        client: Unused (kept for signature compat).

    Returns:
        Dict with keys: ``id``, ``name`` (or ``error``).
    """
    try:
        data = await graphql(
            _CREATE_REPLAY_SESSION_COLLECTION,
            {"input": {"name": name}},
        )
        result = data.get("createReplaySessionCollection", {})
        collection = result.get("collection", {})
        if not collection:
            return {"error": "Failed to create collection (no collection in response)"}
        return {"id": collection.get("id"), "name": collection.get("name")}
    except Exception as exc:
        return {"error": str(exc)}
