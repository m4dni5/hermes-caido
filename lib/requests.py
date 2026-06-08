"""HTTP request operations for the Caido Python SDK CLI.

Wraps the Caido SDK RequestSDK for searching, retrieving, and exporting
HTTP requests.  Every public async function accepts an optional ``client``
keyword; when omitted a shared client is obtained from ``lib.client``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from client import get_client  # noqa: E402

# ---------------------------------------------------------------------------
# Sort-field mapping  (CLI camelCase names → SDK (target, field) tuples)
# ---------------------------------------------------------------------------

_SORT_MAP: dict[str, tuple[str, str]] = {
    "createdAt":      ("req",  "created_at"),
    "host":           ("req",  "host"),
    "method":         ("req",  "method"),
    "path":           ("req",  "path"),
    "query":          ("req",  "query"),
    "ext":            ("req",  "ext"),
    "id":             ("req",  "id"),
    "source":         ("req",  "source"),
    "statusCode":     ("resp", "code"),
    "responseLength": ("resp", "length"),
    "roundtrip":      ("resp", "roundtrip"),
}


# ---------------------------------------------------------------------------
# Raw HTTP message parser helpers
# ---------------------------------------------------------------------------

def _parse_raw_request(raw: bytes | None) -> dict[str, Any]:
    """Parse raw HTTP request bytes into method, path, querystring, headers, and body."""
    if not raw:
        return {"method": "GET", "path": "/", "querystring": "", "headers": [], "body": ""}
    text = raw.decode("utf-8", errors="replace")
    head, _, body = text.partition("\r\n\r\n")
    lines = head.split("\r\n")
    if not lines:
        return {"method": "GET", "path": "/", "querystring": "", "headers": [], "body": body}

    # Request line:  METHOD  path[?query]  HTTP/x.x
    request_line = lines[0]
    parts = request_line.split(" ", 2)
    method = parts[0] if parts else "GET"
    raw_path = parts[1] if len(parts) > 1 else "/"
    path, _, querystring = raw_path.partition("?")

    headers: list[dict[str, str]] = []
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name:
            headers.append({"name": name.strip(), "value": value.strip()})

    return {"method": method, "path": path, "querystring": querystring, "headers": headers, "body": body}


def _parse_raw_response(raw: bytes | None) -> dict[str, Any]:
    """Parse raw HTTP response bytes into status_code, headers, and body."""
    if not raw:
        return {"status_code": 0, "headers": [], "body": ""}
    text = raw.decode("utf-8", errors="replace")
    head, _, body = text.partition("\r\n\r\n")
    lines = head.split("\r\n")
    if not lines:
        return {"status_code": 0, "headers": [], "body": body}

    # Status line:  HTTP/x.x  200  OK
    status_line = lines[0]
    sparts = status_line.split(" ", 2)
    try:
        status_code = int(sparts[1]) if len(sparts) > 1 else 0
    except ValueError:
        status_code = 0

    headers: list[dict[str, str]] = []
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name:
            headers.append({"name": name.strip(), "value": value.strip()})

    return {"status_code": status_code, "headers": headers, "body": body}


# ---------------------------------------------------------------------------
# SDK-object → plain-dict conversion
# ---------------------------------------------------------------------------

def map_request(node: Any) -> dict[str, Any]:
    """Convert an SDK ``RequestResponseOpt`` (edge node) to a plain dict.

    The returned dict matches the shape expected by ``lib.output``
    (camelCase keys for JSON serialisation).
    """
    req = node.request
    resp = node.response

    # Build URL
    scheme = "https" if req.is_tls else "http"
    default_port = 443 if req.is_tls else 80
    port_part = "" if req.port == default_port else f":{req.port}"
    url = f"{scheme}://{req.host}{port_part}{req.path}"
    if req.query:
        url += f"?{req.query}"

    # Parse raw request/response
    parsed_req = _parse_raw_request(req.raw)
    parsed_resp = _parse_raw_response(resp.raw) if resp else {"status_code": 0, "headers": [], "body": ""}

    return {
        "id":              str(req.id),
        "host":            req.host,
        "port":            req.port,
        "method":          req.method,
        "path":            req.path,
        "querystring":     req.query,
        "url":             url,
        "isTls":           req.is_tls,
        "createdAt":       req.created_at.isoformat() if req.created_at else None,
        "requestHeaders":  parsed_req["headers"],
        "requestBody":     parsed_req["body"],
        "requestLength":   len(req.raw) if req.raw else 0,
        "statusCode":      resp.status_code if resp else parsed_resp["status_code"],
        "responseHeaders": parsed_resp["headers"],
        "responseBody":    parsed_resp["body"],
        "responseLength":  resp.length if resp else 0,
        "remoteAddress":   "",   # not exposed by SDK; placeholder
        "matchedScopes":   [],   # not exposed by SDK; placeholder
    }


def _compact_entry(d: dict[str, Any]) -> dict[str, Any]:
    """Return a slim dict suitable for list views (no headers / bodies)."""
    return {
        "id":             d["id"],
        "host":           d["host"],
        "method":         d["method"],
        "path":           d["path"],
        "url":            d["url"],
        "statusCode":     d["statusCode"],
        "requestLength":  d["requestLength"],
        "responseLength": d["responseLength"],
    }


# ---------------------------------------------------------------------------
# Public async helpers
# ---------------------------------------------------------------------------

async def search(
    query: str = "",
    limit: int = 20,
    sort: str = "createdAt",
    order: str = "DESC",
    client: Any | None = None,
) -> dict[str, Any]:
    """HTTPQL search over HTTP requests.

    Returns::

        {"entries": [{id, host, method, path, url, statusCode, ...}], "total": N}
    """
    try:
        c = client or await get_client()
        builder = c.request.list().first(limit)

        # Apply HTTPQL filter when a query is given
        if query:
            builder = builder.filter(query)

        # Apply sorting
        sort_info = _SORT_MAP.get(sort, _SORT_MAP["createdAt"])
        target, field = sort_info
        if order.upper() == "ASC":
            builder = builder.ascending(target, field)
        else:
            builder = builder.descending(target, field)

        connection = await builder
        entries = [_compact_entry(map_request(edge.node)) for edge in connection.edges]
        return {"entries": entries, "total": len(entries)}
    except Exception as exc:
        return {"error": str(exc), "entries": [], "total": 0}


async def recent(
    limit: int = 10,
    client: Any | None = None,
) -> dict[str, Any]:
    """Return the most recent requests (sorted by createdAt DESC)."""
    return await search(query="", limit=limit, sort="createdAt", order="DESC", client=client)


async def get(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a single request by ID with full details (headers, bodies, etc.)."""
    try:
        c = client or await get_client()
        node = await c.request.get(request_id)
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        return map_request(node)
    except Exception as exc:
        return {"error": str(exc)}


async def get_response(
    request_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a request and return formatted response data.

    Returns the full ``map_request`` dict emphasising response-side fields.
    """
    try:
        c = client or await get_client()
        node = await c.request.get(request_id)
        if node is None:
            return {"error": f"Request {request_id!r} not found"}
        data = map_request(node)
        return {
            "id":              data["id"],
            "statusCode":      data["statusCode"],
            "responseHeaders": data["responseHeaders"],
            "responseBody":    data["responseBody"],
            "responseLength":  data["responseLength"],
            "host":            data["host"],
            "method":          data["method"],
            "path":            data["path"],
            "url":             data["url"],
        }
    except Exception as exc:
        return {"error": str(exc)}


async def export_curl(
    request_id: str,
    client: Any | None = None,
) -> str:
    """Fetch a request and return an equivalent ``curl`` command string."""
    try:
        c = client or await get_client()
        node = await c.request.get(request_id)
        if node is None:
            return f"# Error: Request {request_id!r} not found"
        data = map_request(node)

        parts: list[str] = ["curl"]

        method = data.get("method", "GET")
        if method.upper() != "GET":
            parts.append(f"-X {method}")

        for header in data.get("requestHeaders") or []:
            name = header.get("name", "")
            value = header.get("value", "")
            value_escaped = value.replace("'", "'\\''")
            parts.append(f"-H '{name}: {value_escaped}'")

        body = data.get("requestBody") or ""
        if body:
            body_escaped = body.replace("'", "'\\''")
            parts.append(f"-d '{body_escaped}'")

        url = data.get("url", "")
        if url:
            url_escaped = url.replace("'", "'\\''")
            parts.append(f"'{url_escaped}'")

        return " \\\n  ".join(parts)
    except Exception as exc:
        return f"# Error: {exc}"
