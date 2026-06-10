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

_GET_REQUEST = f"""
{_RESPONSE_FRAGMENT}

{_REQUEST_FRAGMENT}

query Request(
  $id: ID!
  $includeRequestRaw: Boolean!
  $includeResponseRaw: Boolean!
) {{
  request(id: $id) {{ ...RequestFull }}
}}
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
# Public async helpers
# ---------------------------------------------------------------------------


async def search(
    query: str = "",
    limit: int = 20,
    sort: str | None = None,
    order: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """HTTPQL search over HTTP requests.

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

        # HTTPQL filter
        if query:
            variables["filter"] = {"code": query}

        # Sorting
        by = _SORT_MAP.get(sort, "CREATED_AT") if sort else "CREATED_AT"
        direction = _ORDER_MAP.get((order or "DESC").upper(), "DESC")
        variables["order"] = {"by": by, "ordering": direction}

        data = await gql(_SEARCH_REQUESTS, variables)
        requests_data = data.get("requests", {})
        edges = requests_data.get("edges", [])

        entries = [
            _compact_entry(_map_node(edge["node"]))
            for edge in edges
            if edge.get("node")
        ]
        return {"entries": entries, "total": len(entries)}
    except Exception as exc:
        return {"error": str(exc), "entries": [], "total": 0}


async def recent(
    limit: int = 20,
    client: Any | None = None,
) -> dict[str, Any]:
    """Return the most recent requests (sorted by createdAt DESC)."""
    return await search(
        query="", limit=limit, sort="createdAt", order="DESC"
    )


async def get(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a single request by ID with full details (including raw bytes)."""
    try:
        gql = client or graphql
        data = await gql(
            _GET_REQUEST,
            {
                "id": request_id,
                "includeRequestRaw": True,
                "includeResponseRaw": True,
            },
        )
        node = data.get("request")
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        return _map_node(node)
    except Exception as exc:
        return {"error": str(exc)}


async def get_response(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a request and return only the response portion."""
    try:
        gql = client or graphql
        data = await gql(
            _GET_REQUEST,
            {
                "id": request_id,
                "includeRequestRaw": True,
                "includeResponseRaw": True,
            },
        )
        node = data.get("request")
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        entry = _map_node(node)
        resp = (node.get("response") or {})
        return {
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
    except Exception as exc:
        return {"error": str(exc)}


async def export_curl(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a request with raw bytes and build an equivalent ``curl`` command.

    Parses the raw HTTP request to extract the method, headers, path, and body,
    then constructs a curl command string.

    Returns ``{"curl": "curl -X GET ..."}`` on success,
    or ``{"error": "..."}`` on failure.
    """
    try:
        gql = client or graphql
        data = await gql(
            _GET_REQUEST,
            {
                "id": request_id,
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
