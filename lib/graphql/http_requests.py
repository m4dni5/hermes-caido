"""HTTP request operations via raw GraphQL using the real Caido schema.

Searches, retrieves, and exports HTTP requests from Caido using the
GraphQL API directly (no Caido Python SDK).  Every public async function
accepts an optional ``client`` keyword; when omitted a ``graphql`` helper
is imported from ``lib.client``.

Uses the actual Caido GraphQL schema:
  - Request type: id, host, port, method, path, query, isTls, metadata,
    createdAt, raw, response { ... }
  - Response type: id, statusCode, roundtripTime, length, createdAt, raw
  - Requests query: paginated with edges/cursor/pageInfo, filter (HTTPQLInput),
    order (RequestResponseOrderInput), scopeId
  - Request query: single request by id
"""

from __future__ import annotations
import base64

import shlex
import sys
from pathlib import Path
from typing import Any


from .client import graphql  # noqa: E402
from .httpql import SYNTAX_HINT, normalize_httpql  # noqa: E402

# Sentinel for distinguishing "not passed" from "explicitly None"
_UNSET = object()

# Module-level active scope — auto-selected by the context envelope
# (lib/graphql/context.py) on the first read call, used by search/recent
_active_scope_id: str | None = None


def set_active_scope(scope_id: str | None) -> None:
    """Set the active scope for search/recent queries."""
    global _active_scope_id
    _active_scope_id = scope_id


def get_active_scope() -> str | None:
    """Return the currently active scope ID, or None."""
    return _active_scope_id


# ---------------------------------------------------------------------------
# GraphQL fragments & queries (real Caido schema)
# ---------------------------------------------------------------------------

_RESPONSE_FRAGMENT = """\
fragment ResponseFull on Response {
  id
  statusCode
  roundtripTime
  length
  createdAt
  raw @include(if: $includeResponseRaw)
}"""

_REQUEST_FRAGMENT = """\
fragment RequestFull on Request {
  id
  host
  port
  method
  path
  query
  isTls
  metadata { id color }
  createdAt
  raw @include(if: $includeRequestRaw)
  response { ...ResponseFull }
}"""

_SEARCH_REQUESTS = f"""
{_RESPONSE_FRAGMENT}

{_REQUEST_FRAGMENT}

query Requests(
  $first: Int
  $after: String
  $last: Int
  $before: String
  $filter: HTTPQLInput
  $order: RequestResponseOrderInput
  $scopeId: ID
  $includeRequestRaw: Boolean!
  $includeResponseRaw: Boolean!
) {{
  requests(
    first: $first
    after: $after
    last: $last
    before: $before
    filter: $filter
    order: $order
    scopeId: $scopeId
  ) {{
    edges {{
      cursor
      node {{ ...RequestFull }}
    }}
    pageInfo {{ hasNextPage hasPreviousPage startCursor endCursor }}
  }}
}}
"""

_GET_REQUEST = f"""\
{_RESPONSE_FRAGMENT}

{_REQUEST_FRAGMENT}

query Request(
  $id: ID!
  $includeRequestRaw: Boolean!
  $includeResponseRaw: Boolean!
) {{
  request(id: $id) {{ ...RequestFull }}
}}"""

# Lightweight lookup that carries both ID namespaces — used by the resolver.
_GET_REQUEST_WITH_METADATA = """\
query RequestWithMetadata($id: ID!) {
  request(id: $id) { id metadata { id } host method path }
}
"""

# The query the Caido UI history table is built on. Pages in ID ASC order.
_REQUESTS_BY_OFFSET = """\
query RequestsByOffset($offset: Int, $limit: Int) {
  requestsByOffset(offset: $offset, limit: $limit) {
    nodes { id metadata { id } host method path }
  }
}
"""

# ---------------------------------------------------------------------------
# Sort-field mapping (CLI camelCase names → GraphQL enum values)
# ---------------------------------------------------------------------------

_SORT_MAP: dict[str, str] = {
    "createdAt":  "CREATED_AT",
    "host":       "HOST",
    "method":     "METHOD",
    "path":       "PATH",
    "statusCode": "STATUS_CODE",
}

_ORDER_MAP: dict[str, str] = {
    "ASC":  "ASC",
    "DESC": "DESC",
}

# ---------------------------------------------------------------------------
# Node → plain-dict mapping
# ---------------------------------------------------------------------------


def _map_node(node: dict[str, Any]) -> dict[str, Any]:
    """Convert a GraphQL Request node to a plain dict for output."""
    resp = node.get("response") or {}
    metadata = node.get("metadata") or {}

    result: dict[str, Any] = {
        "id":          node.get("id", ""),
        "host":        node.get("host", ""),
        "port":        node.get("port", 0),
        "method":      node.get("method", ""),
        "path":        node.get("path", ""),
        "query":       node.get("query", ""),
        "isTls":       node.get("isTls", False),
        "createdAt":   node.get("createdAt"),
        "statusCode":  resp.get("statusCode", 0),
        "roundtripTime": resp.get("roundtripTime", 0),
        "length":      resp.get("length", 0),
        "metadata": {
            "id":    metadata.get("id", ""),
            "color": metadata.get("color", ""),
        },
    }

    # Include raw bytes when fetched (includeRequestRaw/includeResponseRaw=True)
    # Decode base64 (GraphQL Blob type)
    if node.get("raw") is not None:
        try:
            result["requestRaw"] = base64.b64decode(node["raw"]).decode("utf-8")
        except Exception:
            result["requestRaw"] = node["raw"]
    if resp.get("raw") is not None:
        try:
            result["responseRaw"] = base64.b64decode(resp["raw"]).decode("utf-8")
        except Exception:
            result["responseRaw"] = resp["raw"]

    return result


def _compact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a slim dict for list views (no raw bytes)."""
    return {
        "id":            entry["id"],
        "host":          entry["host"],
        "port":          entry["port"],
        "method":        entry["method"],
        "path":          entry["path"],
        "query":         entry["query"],
        "isTls":         entry["isTls"],
        "createdAt":     entry["createdAt"],
        "statusCode":    entry["statusCode"],
        "roundtripTime": entry["roundtripTime"],
        "length":        entry["length"],
        "metadata":      entry["metadata"],
    }


# ---------------------------------------------------------------------------
# ID namespace resolution (Request.id vs UI-visible metadata.id)
# ---------------------------------------------------------------------------

_METADATA_SCAN_PAGE = 400
_METADATA_SCAN_MAX_PAGES = 30


async def _scan_by_metadata(metadata_id: str, client: Any = None) -> list[dict[str, Any]]:
    """Page requestsByOffset (ID ASC) and collect nodes whose metadata.id matches.

    Returns a list of lightweight node dicts (id, metadata, host, method, path).
    Metadata ids are allocated per request-group and are NOT strictly monotonic
    in Request.id order, so we scan the full bounded window rather than
    early-terminating. We can still skip the prefix: a group counter never
    overtakes the request counter, so a node with metadata.id M always has
    Request.id >= M — start the scan at offset M.
    """
    gql = client or graphql
    try:
        start = max(0, int(metadata_id) - 1)
    except (TypeError, ValueError):
        start = 0
    hits: list[dict[str, Any]] = []
    for page in range(_METADATA_SCAN_MAX_PAGES):
        offset = start + page * _METADATA_SCAN_PAGE
        data = await gql(
            _REQUESTS_BY_OFFSET,
            {"offset": offset, "limit": _METADATA_SCAN_PAGE},
        )
        nodes = data.get("requestsByOffset", {}).get("nodes", [])
        if not nodes:
            break
        for node in nodes:
            if node.get("metadata", {}).get("id") == metadata_id:
                hits.append(node)
    return hits


async def _fetch_full(canonical_id: str, client: Any = None) -> dict[str, Any]:
    """Fetch the full mapped node (raw bytes included) for a canonical Request.id."""
    gql = client or graphql
    data = await gql(
        _GET_REQUEST,
        {
            "id": canonical_id,
            "includeRequestRaw": True,
            "includeResponseRaw": True,
        },
    )
    node = data.get("request")
    if node is None:
        return {"error": f"Request {canonical_id!r} not found"}
    return _map_node(node)


async def resolve_request_id(request_id: str, client: Any = None) -> dict[str, Any]:
    """Resolve a user-quoted ID to the canonical Request.id.

    Caido's UI history table displays ``metadata.id`` (a group key), while the
    GraphQL ``request(id:)`` lookup uses ``Request.id``. A number quoted from
    the UI therefore resolves to the wrong request if passed straight through.

    Strategy:
      1. Try ``request(id:)`` directly — accept it only when the returned
         request's own ``metadata.id == requested`` (true fast-path hit).
      2. Otherwise scan ``requestsByOffset`` for nodes whose ``metadata.id ==
         requested`` (the UI-number case). Return the first hit, or the direct
         node as a fallback when nothing matches by metadata.

    Returns a plain dict (mapped node) or ``{"error": ...}``.
    """
    gql = client or graphql
    try:
        data = await gql(_GET_REQUEST_WITH_METADATA, {"id": request_id})
        direct = data.get("request")
    except Exception as exc:
        return {"error": str(exc)}

    if direct:
        direct_meta = (direct.get("metadata") or {}).get("id")
        if direct_meta == request_id:
            return direct

    # UI-number case: scan for a node carrying this metadata.id.
    hits = await _scan_by_metadata(request_id, client=gql)
    if hits:
        # Fetch the full mapped node for the first match.
        first = hits[0]
        full = await _fetch_full(first.get("id", ""), client=gql)
        if isinstance(full, dict) and "error" not in full:
            full["metadata_id"] = request_id
            if len(hits) > 1:
                full["metadata_matches"] = [
                    {"id": n.get("id"), "host": n.get("host"), "method": n.get("method"), "path": n.get("path")}
                    for n in hits
                ]
            # If the same number is also a valid Request.id of a different
            # request, surface that so the agent can disambiguate.
            if direct and direct.get("id") != first.get("id"):
                full["direct_match"] = {
                    "id": direct.get("id"),
                    "host": direct.get("host"),
                    "method": direct.get("method"),
                    "path": direct.get("path"),
                    "note": "Also a valid Request.id — the metadata interpretation was chosen.",
                }
            return full

    if direct:
        return direct
    return {"error": f"Request {request_id!r} not found"}


# ---------------------------------------------------------------------------
# Public async helpers
# ---------------------------------------------------------------------------


async def search(
    query: str = "",
    limit: int = 20,
    sort: str | None = None,
    order: str | None = None,
    scope_id: Any = _UNSET,
    client: Any | None = None,
) -> dict[str, Any]:
    """HTTPQL search over HTTP requests.

    Args:
        query: HTTPQL filter string.
        limit: Max results.
        sort: Sort field (createdAt, host, method, path, statusCode).
        order: ASC or DESC.
        scope_id: Scope ID to filter by. Defaults to active Caido scope.
            Pass None explicitly to disable scope filtering.

    Returns::

        {"entries": [{id, host, port, method, path, statusCode, ...}], "total": N}
    """
    try:
        gql = client or graphql

        variables: dict[str, Any] = {
            "first": limit,
            "includeRequestRaw": False,
            "includeResponseRaw": False,
        }

        # HTTPQL filter — repair common shorthand (missing operators, bare
        # strings, unquoted values) before it reaches the strict parser.
        normalized = ""
        repairs: list[str] = []
        if query:
            normalized, repairs = normalize_httpql(query)
            variables["filter"] = {"code": normalized}

        # Sorting
        by = _SORT_MAP.get(sort, "CREATED_AT") if sort else "CREATED_AT"
        direction = _ORDER_MAP.get((order or "DESC").upper(), "DESC")
        variables["order"] = {"by": by, "ordering": direction}

        # Scope filtering — prefer explicit, fall back to active scope
        if scope_id is _UNSET:
            scope_id = _active_scope_id  # Use active scope if auto-selected
        if scope_id:
            variables["scopeId"] = scope_id

        data = await gql(_SEARCH_REQUESTS, variables)
        requests_data = data.get("requests", {})
        edges = requests_data.get("edges", [])

        entries = [
            _compact_entry(_map_node(edge["node"]))
            for edge in edges
            if edge.get("node")
        ]
        result: dict[str, Any] = {"entries": entries, "total": len(entries)}
        if query and normalized != query:
            result["httpql"] = {"query": normalized, "repairs": repairs}
        return result
    except Exception as exc:
        message = str(exc)
        if "Invalid HTTPQL query" in message:
            message = f"{message} — {SYNTAX_HINT}"
        return {"error": message, "entries": [], "total": 0}


async def recent(
    limit: int = 20,
    scope_id: Any = _UNSET,
    client: Any | None = None,
) -> dict[str, Any]:
    """Return the most recent requests (sorted by createdAt DESC)."""
    return await search(
        query="", limit=limit, sort="createdAt", order="DESC",
        scope_id=scope_id, client=client,
    )


async def get(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a single request by ID with full details (including raw bytes).

    Accepts both the GraphQL ``Request.id`` and the UI-visible ``metadata.id``
    (a number quoted from the Caido history table). Resolves metadata ids via
    a requestsByOffset scan before fetching.
    """
    try:
        gql = client or graphql

        # Resolve UI-visible metadata ids to the canonical Request.id.
        resolved = await resolve_request_id(request_id, client=gql)
        if isinstance(resolved, dict) and "error" in resolved:
            return resolved

        # The resolver already fetched full bytes when it scanned by metadata.
        if resolved.get("requestRaw") is not None:
            return resolved
        canonical_id = resolved.get("id", request_id)

        data = await gql(
            _GET_REQUEST,
            {
                "id": canonical_id,
                "includeRequestRaw": True,
                "includeResponseRaw": True,
            },
        )
        node = data.get("request")
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        result = _map_node(node)
        # Surface the UI number: metadata.id (the group key shown in the Caido
        # UI history table). Always present, whether we resolved via metadata
        # or the request came from a plain Request.id lookup.
        result["metadata_id"] = resolved.get("metadata_id") or (result.get("metadata") or {}).get("id")
        if resolved.get("metadata_matches"):
            result["metadata_matches"] = resolved["metadata_matches"]
        return result
    except Exception as exc:
        return {"error": str(exc)}


async def get_response(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a request and return only the response portion.

    Accepts both the GraphQL ``Request.id`` and the UI-visible ``metadata.id``.
    """
    try:
        gql = client or graphql
        resolved = await resolve_request_id(request_id, client=gql)
        if isinstance(resolved, dict) and "error" in resolved:
            return resolved
        canonical_id = resolved.get("id", request_id)

        data = await gql(
            _GET_REQUEST,
            {
                "id": canonical_id,
                "includeRequestRaw": True,
                "includeResponseRaw": True,
            },
        )
        node = data.get("request")
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        entry = _map_node(node)
        resp = (node.get("response") or {})
        result = {
            "id":            entry["id"],
            "statusCode":    entry["statusCode"],
            "roundtripTime": entry["roundtripTime"],
            "length":        entry["length"],
            "responseRaw":   entry.get("responseRaw", ""),
            "host":          entry["host"],
            "method":        entry["method"],
            "path":          entry["path"],
            "port":          entry["port"],
            "isTls":         entry["isTls"],
        }
        if resolved.get("metadata_id"):
            result["metadata_id"] = resolved["metadata_id"]
        return result
    except Exception as exc:
        return {"error": str(exc)}


async def export_curl(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a request with raw bytes and build an equivalent ``curl`` command.

    Parses the raw HTTP request to extract the method, headers, path, and body,
    then constructs a curl command string.

    Accepts both the GraphQL ``Request.id`` and the UI-visible ``metadata.id``.

    Returns ``{"curl": "curl -X GET ..."}`` on success,
    or ``{"error": "..."}`` on failure.
    """
    try:
        gql = client or graphql
        resolved = await resolve_request_id(request_id, client=gql)
        if isinstance(resolved, dict) and "error" in resolved:
            return resolved
        canonical_id = resolved.get("id", request_id)

        data = await gql(
            _GET_REQUEST,
            {
                "id": canonical_id,
                "includeRequestRaw": True,
                "includeResponseRaw": False,
            },
        )
        node = data.get("request")
        if node is None:
            return {"error": f"Request {request_id!r} not found"}

        raw_b64 = node.get("raw") or ""
        is_tls = node.get("isTls", False)
        host = node.get("host", "")
        port = node.get("port", 443 if is_tls else 80)

        # Decode base64 raw bytes (GraphQL Blob type)
        raw = ""
        if raw_b64:
            try:
                raw = base64.b64decode(raw_b64).decode("utf-8")
            except Exception:
                raw = raw_b64  # Fallback to treating as plain string

        # If we have raw bytes, parse them to build the curl command
        if raw:
            curl_cmd = _raw_to_curl(raw, host, port, is_tls)
            return {"curl": curl_cmd}

        # Fallback: build from structured fields
        method = node.get("method", "GET")
        path = node.get("path", "/")
        query_str = node.get("query", "")
        scheme = "https" if is_tls else "http"
        default_port = 443 if is_tls else 80
        port_suffix = f":{port}" if port != default_port else ""
        url = f"{scheme}://{host}{port_suffix}{path}"
        if query_str:
            url += f"?{query_str}"

        parts: list[str] = ["curl", "-sS"]
        if method.upper() != "GET":
            parts.append(f"-X {shlex.quote(method)}")
        parts.append(shlex.quote(url))

        return {"curl": " ".join(parts)}
    except Exception as exc:
        return {"error": str(exc)}


def _raw_to_curl(raw: str, host: str, port: int, is_tls: bool) -> str:
    """Parse a raw HTTP request string and build a curl command."""
    lines = raw.split("\r\n") if "\r\n" in raw else raw.split("\n")
    if not lines:
        return "curl"

    # Parse request line: METHOD /path HTTP/1.1
    request_line = lines[0].split(" ", 2)
    method = request_line[0] if len(request_line) > 0 else "GET"
    path = request_line[1] if len(request_line) > 1 else "/"

    # Parse headers and find body
    headers: list[tuple[str, str]] = []
    body = ""
    in_body = False
    for line in lines[1:]:
        if in_body:
            body += line
            continue
        if line.strip() == "":
            in_body = True
            continue
        if ":" in line:
            name, _, value = line.partition(":")
            headers.append((name.strip(), value.strip()))

    # Build URL from request line path + host header
    # The path in raw request is typically absolute (/path?query)
    scheme = "https" if is_tls else "http"
    default_port = 443 if is_tls else 80
    port_suffix = f":{port}" if port != default_port else ""
    url = f"{scheme}://{host}{port_suffix}{path}"

    # Build curl command
    parts: list[str] = ["curl", "-sS"]
    if method.upper() != "GET":
        parts.append(f"-X {shlex.quote(method)}")

    for name, value in headers:
        # Skip Host header — curl sets it automatically from the URL
        if name.lower() == "host":
            continue
        parts.append(f"-H {shlex.quote(f'{name}: {value}')}")

    if body:
        parts.append(f"-d {shlex.quote(body)}")

    parts.append(shlex.quote(url))
    return " ".join(parts)
