"""Automate operations via raw GraphQL.

Session CRUD and task management for Caido's Automate (fuzzer).
Matches the real Caido GraphQL schema.

Workflow:
1. create_session(request_id) — create from proxy history
2. update_session(id, raw, connection, settings) — configure placeholders, payloads, strategy
3. start_task(session_id) — fire
4. get_entry_requests(entry_id, filter, order) — retrieve results
"""

from __future__ import annotations

import base64
from typing import Any

from .client import graphql

# ---------------------------------------------------------------------------
# GraphQL fragments
# ---------------------------------------------------------------------------

_FRAGMENT_CONNECTION_INFO = """\
fragment ConnectionInfoFields on ConnectionInfo {
  host
  port
  isTLS
  SNI
}"""

_FRAGMENT_AUTOMATE_SETTINGS = """\
fragment AutomateSettingsFields on AutomateSettings {
  closeConnection
  updateContentLength
  strategy
  concurrency { workers delay }
  redirect { strategy max }
  retryOnFailure { backoff maximumRetries }
  placeholders { start end }
  payloads {
    options {
      __typename
      ... on AutomateSimpleListPayload { list }
      ... on AutomateNumberPayload { range { start end } increments minLength }
      ... on AutomateHostedFilePayload { id delimiter }
      ... on AutomateNullPayload { quantity }
    }
    preprocessors {
      options {
        __typename
        ... on AutomatePrefixPreprocessor { value }
        ... on AutomateSuffixPreprocessor { value }
        ... on AutomateUrlEncodePreprocessor { charset nonAscii }
        ... on AutomateWorkflowPreprocessor { id }
      }
    }
  }
  extractors {
    __typename
    ... on AutomateExtractorRegex { body regex workflowId }
  }
}"""

_FRAGMENT_AUTOMATE_ENTRY = """\
fragment AutomateEntryFields on AutomateEntry {
  id
  name
  createdAt
  raw
  connection { ...ConnectionInfoFields }
  settings { ...AutomateSettingsFields }
}"""

_FRAGMENT_AUTOMATE_SESSION = f"""\
{_FRAGMENT_CONNECTION_INFO}
{_FRAGMENT_AUTOMATE_SETTINGS}
{_FRAGMENT_AUTOMATE_ENTRY}

fragment AutomateSessionFields on AutomateSession {{
  id
  name
  createdAt
  raw
  connection {{ ...ConnectionInfoFields }}
  settings {{ ...AutomateSettingsFields }}
  entries {{ ...AutomateEntryFields }}
}}"""

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

_AUTOMATE_SESSIONS = f"""\
{_FRAGMENT_AUTOMATE_SESSION}

query AutomateSessions($first: Int) {{
  automateSessions(first: $first) {{
    edges {{ node {{ ...AutomateSessionFields }} }}
  }}
}}"""

_AUTOMATE_SESSION = f"""\
{_FRAGMENT_AUTOMATE_SESSION}

query AutomateSession($id: ID!) {{
  automateSession(id: $id) {{ ...AutomateSessionFields }}
}}"""

# ---------------------------------------------------------------------------
# GraphQL mutations
# ---------------------------------------------------------------------------

_CREATE_AUTOMATE_SESSION = """\
mutation CreateAutomateSession($input: CreateAutomateSessionInput!) {
  createAutomateSession(input: $input) {
    session { id name }
  }
}"""

_RENAME_AUTOMATE_SESSION = """\
mutation RenameAutomateSession($id: ID!, $name: String!) {
  renameAutomateSession(id: $id, name: $name) {
    session { id name }
  }
}"""

_UPDATE_AUTOMATE_SESSION = """\
mutation UpdateAutomateSession($id: ID!, $input: UpdateAutomateSessionInput!) {
  updateAutomateSession(id: $id, input: $input) {
    session { id name }
    error { __typename ... on PermissionDeniedUserError { code } ... on CloudUserError { code } ... on OtherUserError { code } }
  }
}"""

_DELETE_AUTOMATE_SESSION = """\
mutation DeleteAutomateSession($id: ID!) {
  deleteAutomateSession(id: $id) {
    deletedId
  }
}"""

_DUPLICATE_AUTOMATE_SESSION = """\
mutation DuplicateAutomateSession($id: ID!) {
  duplicateAutomateSession(id: $id) {
    session { id name }
  }
}"""

_START_AUTOMATE_TASK = """\
mutation StartAutomateTask($automateSessionId: ID!) {
  startAutomateTask(automateSessionId: $automateSessionId) {
    automateTask { id paused entry { id } }
  }
}"""

_CANCEL_AUTOMATE_TASK = """\
mutation CancelAutomateTask($id: ID!) {
  cancelAutomateTask(id: $id) {
    cancelledId
    userError { __typename ... on UnknownIdUserError { code } ... on OtherUserError { code } }
  }
}"""

_PAUSE_AUTOMATE_TASK = """\
mutation PauseAutomateTask($id: ID!) {
  pauseAutomateTask(id: $id) {
    automateTask { id paused }
    userError { __typename ... on UnknownIdUserError { code } ... on OtherUserError { code } }
  }
}"""

_RESUME_AUTOMATE_TASK = """\
mutation ResumeAutomateTask($id: ID!) {
  resumeAutomateTask(id: $id) {
    automateTask { id paused }
    userError { __typename ... on UnknownIdUserError { code } ... on OtherUserError { code } }
  }
}"""

_AUTOMATE_TASKS = """\
query AutomateTasks($first: Int) {
  automateTasks(first: $first) {
    edges {
      node {
        id
        paused
        entry { id name }
      }
    }
  }
}"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_session(node: dict[str, Any]) -> dict[str, Any]:
    """Parse an AutomateSession GraphQL node into a plain dict."""
    result = {
        "id": node.get("id", ""),
        "name": node.get("name", ""),
        "createdAt": node.get("createdAt"),
        "raw": node.get("raw", ""),
        "connection": node.get("connection", {}),
        "settings": node.get("settings", {}),
        "entries": [],
    }
    for entry in node.get("entries", []):
        result["entries"].append({
            "id": entry.get("id", ""),
            "name": entry.get("name", ""),
            "createdAt": entry.get("createdAt"),
            "raw": entry.get("raw", ""),
            "connection": entry.get("connection", {}),
            "settings": entry.get("settings", {}),
        })
    return result


# ---------------------------------------------------------------------------
# Public API — sessions
# ---------------------------------------------------------------------------


async def sessions(limit: int = 50, client=None) -> list:
    """List automate sessions.

    Returns:
        List of dicts with ``id``, ``name``, ``createdAt``, ``connection``,
        ``settings``, ``entries``.
    """
    try:
        data = await graphql(_AUTOMATE_SESSIONS, {"first": limit})
        edges = data.get("automateSessions", {}).get("edges", [])
        return [
            _parse_session(edge["node"])
            for edge in edges
            if edge.get("node")
        ]
    except Exception as exc:
        return [{"error": str(exc)}]


async def get_session(session_id: str, client=None) -> dict:
    """Get an automate session with its entries and settings.

    Args:
        session_id: ID of the session to retrieve.

    Returns:
        Dict with ``id``, ``name``, ``createdAt``, ``connection``,
        ``settings``, ``entries``.
    """
    try:
        data = await graphql(_AUTOMATE_SESSION, {"id": session_id})
        node = data.get("automateSession")
        if not node:
            return {"error": f"Session {session_id!r} not found"}
        return _parse_session(node)
    except Exception as exc:
        return {"error": str(exc)}


async def create_session(request_id: str | None = None, client=None) -> dict:
    """Create a new automate session.

    Args:
        request_id: Optional proxy request ID to seed the session from.

    Returns:
        Dict with ``id``, ``name`` (or ``error``).
    """
    try:
        input_vars: dict[str, Any] = {}
        if request_id:
            input_vars["requestSource"] = {"id": request_id}
        data = await graphql(_CREATE_AUTOMATE_SESSION, {"input": input_vars})
        result = data.get("createAutomateSession", {})
        session = result.get("session", {})
        if not session:
            return {"error": "Failed to create session (no session in response)"}
        return {"id": session.get("id"), "name": session.get("name", "")}
    except Exception as exc:
        return {"error": str(exc)}


async def rename_session(session_id: str, name: str, client=None) -> dict:
    """Rename an automate session."""
    try:
        data = await graphql(_RENAME_AUTOMATE_SESSION, {"id": session_id, "name": name})
        result = data.get("renameAutomateSession", {})
        session = result.get("session", {})
        if not session:
            return {"error": "Failed to rename session"}
        return {"id": session.get("id"), "name": session.get("name")}
    except Exception as exc:
        return {"error": str(exc)}


async def update_session(
    session_id: str,
    raw: str | None = None,
    connection: dict | None = None,
    settings: dict | None = None,
    client=None,
) -> dict:
    """Update an automate session's raw request, connection, or settings.

    Args:
        session_id: ID of the session to update.
        raw: New raw HTTP request (will be base64-encoded).
        connection: ConnectionInfoInput dict {host, port, isTLS, SNI?}.
        settings: AutomateSettingsInput dict with placeholders, payloads, etc.

    Returns:
        Dict with ``id``, ``name`` (or ``error``).
    """
    try:
        import base64 as _b64
        input_vars: dict[str, Any] = {}
        if raw is not None:
            input_vars["raw"] = _b64.b64encode(raw.encode("utf-8")).decode("utf-8")
        if connection is not None:
            input_vars["connection"] = connection
        if settings is not None:
            input_vars["settings"] = settings
        if not input_vars:
            return {"error": "No fields to update"}
        data = await graphql(_UPDATE_AUTOMATE_SESSION, {"id": session_id, "input": input_vars})
        result = data.get("updateAutomateSession", {})
        if result.get("error"):
            err = result["error"]
            return {"error": f"{err.get('__typename', 'Unknown')}: {err.get('code', '')}"}
        session = result.get("session", {})
        if not session:
            return {"error": "Failed to update session"}
        return {"id": session.get("id"), "name": session.get("name")}
    except Exception as exc:
        return {"error": str(exc)}


async def delete_session(session_id: str, client=None) -> dict:
    """Delete an automate session."""
    try:
        data = await graphql(_DELETE_AUTOMATE_SESSION, {"id": session_id})
        result = data.get("deleteAutomateSession", {})
        deleted_id = result.get("deletedId")
        if not deleted_id:
            return {"error": "Failed to delete session"}
        return {"id": deleted_id}
    except Exception as exc:
        return {"error": str(exc)}


async def duplicate_session(session_id: str, client=None) -> dict:
    """Duplicate an automate session."""
    try:
        data = await graphql(_DUPLICATE_AUTOMATE_SESSION, {"id": session_id})
        result = data.get("duplicateAutomateSession", {})
        session = result.get("session", {})
        if not session:
            return {"error": "Failed to duplicate session"}
        return {"id": session.get("id"), "name": session.get("name", "")}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Public API — tasks
# ---------------------------------------------------------------------------


async def start_task(session_id: str, client=None) -> dict:
    """Start an automate task from a session.

    Args:
        session_id: ID of the automate session to run.

    Returns:
        Dict with ``taskId``, ``paused``, ``entryId`` (or ``error``).
    """
    try:
        data = await graphql(_START_AUTOMATE_TASK, {"automateSessionId": session_id})
        result = data.get("startAutomateTask", {})
        task = result.get("automateTask", {})
        if not task:
            return {"error": "Failed to start task"}
        return {
            "taskId": task.get("id"),
            "paused": task.get("paused"),
            "entryId": (task.get("entry") or {}).get("id"),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def list_tasks(limit: int = 50, client=None) -> list:
    """List automate tasks.

    Returns:
        List of dicts with ``id``, ``paused``, ``entryId``, ``entryName``.
    """
    try:
        data = await graphql(_AUTOMATE_TASKS, {"first": limit})
        edges = data.get("automateTasks", {}).get("edges", [])
        results = []
        for edge in edges:
            node = edge.get("node", {})
            entry = node.get("entry") or {}
            results.append({
                "id": node.get("id"),
                "paused": node.get("paused"),
                "entryId": entry.get("id"),
                "entryName": entry.get("name"),
            })
        return results
    except Exception as exc:
        return [{"error": str(exc)}]


async def cancel_task(task_id: str, client=None) -> dict:
    """Cancel an automate task."""
    try:
        data = await graphql(_CANCEL_AUTOMATE_TASK, {"id": task_id})
        result = data.get("cancelAutomateTask", {})
        if result.get("userError"):
            err = result["userError"]
            return {"error": f"{err.get('__typename', 'Unknown')}: {err.get('code', '')}"}
        cancelled_id = result.get("cancelledId")
        if not cancelled_id:
            return {"error": "Failed to cancel task"}
        return {"id": cancelled_id}
    except Exception as exc:
        return {"error": str(exc)}


async def pause_task(task_id: str, client=None) -> dict:
    """Pause a running automate task."""
    try:
        data = await graphql(_PAUSE_AUTOMATE_TASK, {"id": task_id})
        result = data.get("pauseAutomateTask", {})
        if result.get("userError"):
            err = result["userError"]
            return {"error": f"{err.get('__typename', 'Unknown')}: {err.get('code', '')}"}
        task = result.get("automateTask", {})
        return {"id": task.get("id"), "paused": task.get("paused")}
    except Exception as exc:
        return {"error": str(exc)}


async def resume_task(task_id: str, client=None) -> dict:
    """Resume a paused automate task."""
    try:
        data = await graphql(_RESUME_AUTOMATE_TASK, {"id": task_id})
        result = data.get("resumeAutomateTask", {})
        if result.get("userError"):
            err = result["userError"]
            return {"error": f"{err.get('__typename', 'Unknown')}: {err.get('code', '')}"}
        task = result.get("automateTask", {})
        return {"id": task.get("id"), "paused": task.get("paused")}
    except Exception as exc:
        return {"error": str(exc)}
