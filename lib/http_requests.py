"""HTTP request operations via raw GraphQL.

Searches, retrieves, and exports HTTP requests from Caido using the
GraphQL API directly (no Caido Python SDK).  Every public async function
accepts an optional ``client`` keyword; when omitted a ``graphql`` helper
is imported from ``lib.client``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from client import graphql  # noqa: E402

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

_SEARCH_REQUESTS = """
query SearchRequests($input: SearchInput!) {
  requests(input: $input) {
    edges {
      node {
        id
        host
        method
        path
        query
        url
        createdAt
        source
        request {
          headers { name value }
          body
          headerSize
        }
        response {
          code
          headers { name value }
          body
          bodySize
        }
      }
    }
    totalCount
  }
}
"""

_GET_REQUEST = """
query GetRequest($id: ID!) {
  request(id: $id) {
    id
    host
    method
    path
    query
    url
    createdAt
    source
    request {
      headers { name value }
      body
      headerSize
    }
    response {
      code
      headers { name value }
      body
      bodySize
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Sort-field mapping (CLI camelCase names → GraphQL OrderByEnum values)
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
    """Convert a GraphQL edge node to a plain dict for output."""
    req = node.get("request") or {}
    resp = node.get("response") or {}

    return {
        "id":              node.get("id", ""),
        "host":            node.get("host", ""),
        "method":          node.get("method", ""),
        "path":            node.get("path", ""),
        "query":           node.get("query", ""),
        "url":             node.get("url", ""),
        "createdAt":       node.get("createdAt"),
        "source":          node.get("source", ""),
        "statusCode":      resp.get("code", 0),
        "request": {
            "headers": req.get("headers") or [],
            "body":    req.get("body", ""),
        },
        "response": {
            "code":    resp.get("code", 0),
            "headers": resp.get("headers") or [],
            "body":    resp.get("body", ""),
            "bodySize": resp.get("bodySize", 0),
        },
    }


def _compact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a slim dict for list views (no headers / bodies)."""
    return {
        "id":         entry["id"],
        "host":       entry["host"],
        "method":     entry["method"],
        "path":       entry["path"],
        "url":        entry["url"],
        "statusCode": entry["statusCode"],
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

        {"entries": [{id, host, method, path, url, statusCode, ...}], "total": N}
    """
    try:
        gql = client or graphql

        # Build SearchInput
        search_input: dict[str, Any] = {
            "limit": limit,
            "offset": 0,
        }
        if query:
            search_input["httpql"] = query

        # Sorting
        by = _SORT_MAP.get(sort, "CREATED_AT") if sort else "CREATED_AT"
        direction = _ORDER_MAP.get((order or "DESC").upper(), "DESC")
        search_input["order"] = {"by": by, "direction": direction}

        data = await gql(_SEARCH_REQUESTS, {"input": search_input})
        requests_data = data.get("requests", {})
        edges = requests_data.get("edges", [])
        total = requests_data.get("totalCount", len(edges))

        entries = [_compact_entry(_map_node(edge["node"])) for edge in edges if edge.get("node")]
        return {"entries": entries, "total": total}
    except Exception as exc:
        return {"error": str(exc), "entries": [], "total": 0}


async def recent(
    limit: int = 20,
    client: Any | None = None,
) -> dict[str, Any]:
    """Return the most recent requests (sorted by createdAt DESC)."""
    return await search(query="", limit=limit, sort="createdAt", order="DESC", client=client)


async def get(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a single request by ID with full details."""
    try:
        gql = client or graphql
        data = await gql(_GET_REQUEST, {"id": request_id})
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
        data = await gql(_GET_REQUEST, {"id": request_id})
        node = data.get("request")
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        entry = _map_node(node)
        return {
            "id":              entry["id"],
            "statusCode":      entry["statusCode"],
            "responseHeaders": entry["response"]["headers"],
            "responseBody":    entry["response"]["body"],
            "responseBodySize": entry["response"]["bodySize"],
            "host":            entry["host"],
            "method":          entry["method"],
            "path":            entry["path"],
            "url":             entry["url"],
        }
    except Exception as exc:
        return {"error": str(exc)}


async def export_curl(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a request and return an equivalent ``curl`` command.

    Returns ``{"curl": "curl -X GET ..."}`` on success,
    or ``{"error": "..."}`` on failure.
    """
    try:
        gql = client or graphql
        data = await gql(_GET_REQUEST, {"id": request_id})
        node = data.get("request")
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        entry = _map_node(node)

        parts: list[str] = ["curl"]

        method = entry.get("method", "GET")
        if method.upper() != "GET":
            parts.append(f"-X {method}")

        for header in entry.get("request", {}).get("headers") or []:
            name = header.get("name", "")
            value = header.get("value", "")
            value_escaped = value.replace("'", "'\\''")
            parts.append(f"-H '{name}: {value_escaped}'")

        body = entry.get("request", {}).get("body") or ""
        if body:
            body_escaped = body.replace("'", "'\\''")
            parts.append(f"-d '{body_escaped}'")

        url = entry.get("url", "")
        if url:
            url_escaped = url.replace("'", "'\\''")
            parts.append(f"'{url_escaped}'")

        return {"curl": " \\\n  ".join(parts)}
    except Exception as exc:
        return {"error": str(exc)}
