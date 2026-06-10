"""Replay operations for the Caido plugin.

Uses raw GraphQL queries via the client module — no SDK dependency.
Matches the real Caido v0.57.0 GraphQL schema.

Replay workflow (v0.57.0):
1. create_session(name, request_id) — creates session seeded with request
2. rename_session(session_id, name) — give it a descriptive name
3. start_replay_task(session_id) — replay the entry in the session

Edit-and-replay workflow:
1. create_session(request_id) — seed session
2. get_session_entries(session_id) — get entry IDs and raw
3. update_entry_draft(entry_id, raw, host, port, is_tls) — modify entry
4. start_replay_task(session_id) — replay modified entry
"""

from __future__ import annotations
import base64
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

_REPLAY_SESSION = """
query ReplaySession($id: ID!) {
  replaySession(id: $id) {
    id
    name
    ... on ReplaySessionHttp {
      entries(first: 50) {
        edges {
          node {
            id
            ... on ReplayEntryHttp {
              raw
              connection { host port isTLS }
              draft {
                raw
                connection { host port isTLS }
              }
              request { id method path host }
            }
          }
        }
      }
    }
  }
}"""

_REPLAY_ENTRY = """
query ReplayEntry($id: ID!, $sessionKind: ReplaySessionKind!) {
  replayEntry(id: $id, sessionKind: $sessionKind) {
    id
    ... on ReplayEntryHttp {
      raw
      connection { host port isTLS }
      draft {
        raw
        connection { host port isTLS }
      }
      request { id method path host }
    }
  }
}"""

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

_UPDATE_REPLAY_ENTRY_DRAFT = """mutation UpdateReplayEntryDraft($id: ID!, $input: UpdateReplayEntryDraftInput!) {
  updateReplayEntryDraft(id: $id, input: $input) {
    entry { id }
  }
}"""

_CLEAR_REPLAY_ENTRY_DRAFT = """mutation ClearReplayEntryDraft($id: ID!, $kind: ReplaySessionKind!) {
  clearReplayEntryDraft(id: $id, kind: $kind) {
    entry { id }
  }
}"""

# ---------------------------------------------------------------------------
# Public API — sessions
# ---------------------------------------------------------------------------


async def sessions(limit: int = 50, client=None) -> list:
    """List replay sessions.

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


async def get_session(session_id: str, client=None) -> dict:
    """Get a replay session with its entries.

    Args:
        session_id: ID of the session to retrieve.

    Returns:
        Dict with ``id``, ``name``, ``entries`` (list of entry dicts).
        Each entry has: ``id``, ``raw``, ``connection``, ``draft``, ``request``.
    """
    try:
        data = await graphql(_REPLAY_SESSION, {"id": session_id})
        session = data.get("replaySession", {})
        if not session:
            return {"error": f"Session {session_id!r} not found"}

        result = {
            "id": session.get("id"),
            "name": session.get("name"),
            "entries": [],
        }

        # Parse entries from relay connection
        entries_connection = session.get("entries", {})
        edges = entries_connection.get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            entry = _parse_entry(node)
            result["entries"].append(entry)

        return result
    except Exception as exc:
        return {"error": str(exc)}


async def get_session_entries(session_id: str, client=None) -> list:
    """Get entries from a replay session.

    Args:
        session_id: ID of the session.

    Returns:
        List of entry dicts, each with: ``id``, ``raw``, ``connection``, ``draft``, ``request``.
    """
    result = await get_session(session_id)
    if "error" in result:
        return [result]
    return result.get("entries", [])


async def get_entry(entry_id: str, client=None) -> dict:
    """Get a specific replay entry by ID.

    Args:
        entry_id: ID of the entry.

    Returns:
        Dict with ``id``, ``raw``, ``connection``, ``draft``, ``request``.
    """
    try:
        data = await graphql(_REPLAY_ENTRY, {"id": entry_id, "sessionKind": "HTTP"})
        entry = data.get("replayEntry", {})
        if not entry:
            return {"error": f"Entry {entry_id!r} not found"}
        return _parse_entry(entry)
    except Exception as exc:
        return {"error": str(exc)}


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
    """Rename a replay session."""
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
    """Delete replay sessions by ID."""
    try:
        data = await graphql(_DELETE_REPLAY_SESSIONS, {"ids": ids})
        result = data.get("deleteReplaySessions", {})
        deleted_ids = result.get("deletedIds", [])
        return {"deleted": len(deleted_ids), "ids": deleted_ids}
    except Exception as exc:
        return {"error": str(exc)}


async def move_session(session_id: str, collection_id: str, client=None) -> dict:
    """Move a replay session to a collection."""
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


# ---------------------------------------------------------------------------
# Public API — entries
# ---------------------------------------------------------------------------


async def update_entry_draft(
    entry_id: str,
    raw: str,
    host: str,
    port: int = 443,
    is_tls: bool = True,
    client=None,
) -> dict:
    """Update a replay entry's draft with modified raw request.

    Args:
        entry_id: ID of the entry to update.
        raw:      Raw HTTP request string (will be base64-encoded).
        host:     Target host.
        port:     Target port (default 443).
        is_tls:   Whether to use TLS (default True).

    Returns:
        Dict with ``id`` of updated entry (or ``error``).
    """
    try:
        raw_b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        editor_state = base64.b64encode(b"{}").decode("utf-8")

        data = await graphql(_UPDATE_REPLAY_ENTRY_DRAFT, {
            "id": entry_id,
            "input": {
                "http": {
                    "raw": raw_b64,
                    "connection": {
                        "host": host,
                        "port": port,
                        "isTLS": is_tls,
                    },
                    "settings": {"placeholders": []},
                    "editorState": editor_state,
                }
            }
        })
        result = data.get("updateReplayEntryDraft", {})
        entry = result.get("entry", {})
        if not entry:
            return {"error": "Failed to update entry draft"}
        return {"id": entry.get("id")}
    except Exception as exc:
        return {"error": str(exc)}


async def clear_entry_draft(entry_id: str, client=None) -> dict:
    """Clear a replay entry's draft, reverting to original.

    Args:
        entry_id: ID of the entry to clear.

    Returns:
        Dict with ``id`` of cleared entry (or ``error``).
    """
    try:
        data = await graphql(_CLEAR_REPLAY_ENTRY_DRAFT, {
            "id": entry_id,
            "kind": "HTTP",
        })
        result = data.get("clearReplayEntryDraft", {})
        entry = result.get("entry", {})
        if not entry:
            return {"error": "Failed to clear entry draft"}
        return {"id": entry.get("id")}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Public API — composite workflows
# ---------------------------------------------------------------------------


async def replay(request_id: str, client=None) -> dict:
    """Replay an existing request by its request ID.

    v0.57.0 workflow: create session with requestSource.id, then start task.

    Returns:
        Dict with ``status``, ``sessionId``, ``taskId`` (or ``error``).
    """
    try:
        session_result = await create_session(request_id=request_id)
        if "error" in session_result:
            return session_result
        session_id = session_result["id"]
        return await start_replay_task(session_id)
    except Exception as exc:
        return {"error": str(exc)}


async def replay_with_edit(
    request_id: str,
    path: str | None = None,
    method: str | None = None,
    headers: list[tuple[str, str]] | None = None,
    body: str | None = None,
    session_name: str | None = None,
    client=None,
) -> dict:
    """Edit a request and replay it in one call.

    Fetches the request, applies mutations to the raw HTTP, creates a
    replay session, updates the entry draft, and starts the replay.

    Args:
        request_id:   ID of the request to edit and replay.
        path:         New path (e.g., "/api/admin/users").
        method:       New HTTP method (e.g., "POST").
        headers:      List of (name, value) tuples to set/replace.
        body:         New request body (auto-updates Content-Length).
        session_name: Optional name for the replay session.

    Returns:
        Dict with ``status``, ``sessionId``, ``taskId``, ``mutations`` (or ``error``).
    """
    try:
        from http_requests import get as get_request

        # Step 1: Fetch the request
        req = await get_request(request_id=request_id)
        if "error" in req:
            return req

        raw = req.get("requestRaw", "")
        if not raw:
            return {"error": f"Request {request_id!r} has no raw bytes"}

        host = req.get("host", "")
        port = req.get("port", 443)
        is_tls = req.get("isTls", True)

        # Step 2: Parse and mutate
        lines = raw.split("\r\n") if "\r\n" in raw else raw.split("\n")
        request_line = lines[0]
        req_headers = []
        req_body = ""
        in_body = False

        for line in lines[1:]:
            if in_body:
                req_body += line
                continue
            if line.strip() == "":
                in_body = True
                continue
            if ":" in line:
                req_headers.append(line)

        mutations = []

        # Apply method/path changes
        parts = request_line.split(" ", 2)
        if method:
            mutations.append(f"method: {parts[0]} -> {method}")
            parts[0] = method
        if path:
            mutations.append(f"path: {parts[1]} -> {path}")
            parts[1] = path
        request_line = " ".join(parts)

        # Apply header changes
        if headers:
            for name, value in headers:
                req_headers = [h for h in req_headers if not h.lower().startswith(name.lower() + ":")]
                req_headers.append(f"{name}: {value}")
                mutations.append(f"header: {name}: {value}")

        # Apply body changes
        if body is not None:
            req_body = body
            req_headers = [h for h in req_headers if not h.lower().startswith("content-length:")]
            req_headers.append(f"Content-Length: {len(body)}")
            mutations.append(f"body: {len(body)} bytes")

        # Reconstruct raw request
        modified_raw = request_line + "\r\n"
        modified_raw += "\r\n".join(req_headers) + "\r\n"
        modified_raw += "\r\n" + req_body

        # Step 3: Create session from original request
        session = await create_session(
            name=session_name or f"edit-{request_id}",
            request_id=request_id,
        )
        if "error" in session:
            return session

        session_id = session["id"]

        # Step 4: Get entry ID
        entries = await get_session_entries(session_id)
        if not entries or "error" in entries[0]:
            return {"error": "Failed to get session entries"}

        entry_id = entries[0]["id"]

        # Step 5: Update entry draft
        draft_result = await update_entry_draft(
            entry_id=entry_id,
            raw=modified_raw,
            host=host,
            port=port,
            is_tls=is_tls,
        )
        if "error" in draft_result:
            return draft_result

        # Step 6: Start replay
        replay_result = await start_replay_task(session_id)
        if "error" in replay_result:
            return replay_result

        return {
            **replay_result,
            "mutations": mutations,
        }
    except Exception as exc:
        return {"error": str(exc)}


async def start_replay_task(session_id: str, client=None) -> dict:
    """Start a replay task on an existing session."""
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


# ---------------------------------------------------------------------------
# Public API — collections
# ---------------------------------------------------------------------------


async def collections(limit: int = 50, client=None) -> list:
    """List replay session collections."""
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
    """Create a replay session collection."""
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_entry(node: dict) -> dict:
    """Parse a ReplayEntryHttp GraphQL node into a plain dict."""
    connection = node.get("connection") or {}
    draft = node.get("draft")
    request = node.get("request")

    entry = {
        "id": node.get("id"),
        "connection": {
            "host": connection.get("host", ""),
            "port": connection.get("port", 0),
            "isTLS": connection.get("isTLS", False),
        },
        "request": None,
        "draft": None,
    }

    # Decode raw bytes
    raw_b64 = node.get("raw", "")
    if raw_b64:
        try:
            entry["raw"] = base64.b64decode(raw_b64).decode("utf-8")
        except Exception:
            entry["raw"] = raw_b64

    # Parse linked request
    if request:
        entry["request"] = {
            "id": request.get("id"),
            "method": request.get("method"),
            "path": request.get("path"),
            "host": request.get("host"),
        }

    # Parse draft
    if draft:
        draft_raw_b64 = draft.get("raw", "")
        draft_raw = ""
        if draft_raw_b64:
            try:
                draft_raw = base64.b64decode(draft_raw_b64).decode("utf-8")
            except Exception:
                draft_raw = draft_raw_b64
        draft_connection = draft.get("connection") or {}
        entry["draft"] = {
            "raw": draft_raw,
            "connection": {
                "host": draft_connection.get("host", ""),
                "port": draft_connection.get("port", 0),
                "isTLS": draft_connection.get("isTLS", False),
            },
        }

    return entry
