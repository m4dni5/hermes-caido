"""Replay operations for the Caido plugin.

Uses raw GraphQL queries via the client module — no SDK dependency.
Matches the real Caido v0.57.0 GraphQL schema.

Replay workflow (v0.57.0):
1. create_session(name, request_id) — creates session seeded with request
2. rename_session(session_id, name) — give it a descriptive name
3. start_replay_task(session_id) — replay the entry in the session
"""

from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client import graphql  # noqa: E402

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

_START_REPLAY_TASK = """mutation StartReplayTask($sessionId: ID!) {
  startReplayTask(sessionId: $sessionId) {
    error {
      __typename
      ... on CloudUserError { code }
      ... on OtherUserError { code }
    }
    task { id }
  }
}"""

_MOVE_REPLAY_SESSION = """mutation MoveReplaySession($id: ID!, $collectionId: ID!) {
  moveReplaySession(id: $id, collectionId: $collectionId) {
    session { id name }
  }
}"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def replay(request_id: str, client=None) -> dict:
    """Replay an existing request by its request ID.

    v0.57.0 workflow: create session with requestSource.id, then start task.

    Args:
        request_id: The ID of an existing request to replay.
        client:     Unused (kept for signature compat).

    Returns:
        Dict with ``status``, ``sessionId``, ``taskId`` (or ``error``).
    """
    try:
        # Step 1: Create session seeded with the request
        session_result = await create_session(request_id=request_id)
        if "error" in session_result:
            return session_result

        session_id = session_result["id"]

        # Step 2: Start replay task
        return await start_replay_task(session_id)
    except Exception as exc:
        return {"error": str(exc)}


async def start_replay_task(session_id: str, client=None) -> dict:
    """Start a replay task on an existing session.

    Args:
        session_id: ID of the session to replay.
        client:     Unused (kept for signature compat).

    Returns:
        Dict with ``status``, ``sessionId``, ``taskId`` (or ``error``).
    """
    try:
        data = await graphql(_START_REPLAY_TASK, {"sessionId": session_id})
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
    request_id: str | None = None,
    collection_id: str | None = None,
    client=None,
) -> dict:
    """Create a new replay session.

    v0.57.0: use requestSource.id to seed session with an existing request.

    Args:
        name:          Optional session name (set via rename after creation).
        request_id:    Optional request ID to seed the session with.
        collection_id: Optional collection to place the session in.
        client:        Unused (kept for signature compat).

    Returns:
        Dict with keys: ``id``, ``name`` (or ``error``).
    """
    try:
        input_vars: dict = {"kind": "HTTP"}
        if request_id:
            input_vars["requestSource"] = {"id": request_id}
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


async def move_session(session_id: str, collection_id: str, client=None) -> dict:
    """Move a replay session to a collection.

    Args:
        session_id:    ID of the session to move.
        collection_id: ID of the target collection.
        client:        Unused (kept for signature compat).

    Returns:
        Dict with updated session info (or ``error``).
    """
    try:
        data = await graphql(
            _MOVE_REPLAY_SESSION,
            {"id": session_id, "collectionId": collection_id},
        )
        result = data.get("moveReplaySession", {})
        session = result.get("session", {})
        if not session:
            return {"error": "Failed to move session (no session in response)"}
        return {"id": session.get("id"), "name": session.get("name")}
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
