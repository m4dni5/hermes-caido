"""Formatting helpers for Caido CLI output.

Simplified for raw GraphQL — all data arrives as plain dicts.
"""

from __future__ import annotations

import json
from typing import Optional


def truncate_body(body: Optional[str], max_length: int = 2000) -> str:
    """Truncate a body string to max_length chars, appending '... (truncated)' if needed.

    Args:
        body: The body string to truncate. May be None or empty.
        max_length: Maximum number of characters to keep.

    Returns:
        The (possibly truncated) body string.
    """
    if not body:
        return ""
    if len(body) <= max_length:
        return body
    return body[:max_length] + "... (truncated)"


def extract_headers(headers: Optional[list[dict]]) -> str:
    """Format a list of {name, value} dicts into 'Name: Value' string.

    Args:
        headers: List of dicts with 'name' and 'value' keys.

    Returns:
        Formatted header string.
    """
    if not headers:
        return ""
    lines = []
    for header in headers:
        name = header.get("name", "")
        value = header.get("value", "")
        lines.append(f"{name}: {value}")
    return "\n".join(lines)


def format_entry_compact(entry: dict) -> str:
    """Format a single request entry in compact mode.

    Takes a dict with id, method, host, path, query, statusCode, createdAt.

    Returns:
        A single line: "{id} {method} {host}{path}[?{query}] [{statusCode}] {createdAt}"
    """
    entry_id = entry.get("id", "?")
    method = entry.get("method", "?")
    host = entry.get("host", "")
    path = entry.get("path", "/")
    query = entry.get("query", "")
    status = entry.get("statusCode", "?")
    length = entry.get("length", 0)
    created = entry.get("createdAt", "")
    # Format length as human-readable
    if length >= 1024 * 1024:
        size = f"{length / 1024 / 1024:.1f}MB"
    elif length >= 1024:
        size = f"{length / 1024:.1f}KB"
    else:
        size = f"{length}B"
    full_path = f"{path}?{query}" if query else path
    return f"{entry_id} {method} {host}{full_path} [{status}] {size} {created}"


def format_curl(request_data: dict) -> str:
    """Convert a request dict to a curl command string.

    Args:
        request_data: A dict with method, host, path, headers, body.

    Returns:
        A curl command string.
    """
    method = request_data.get("method", "GET")
    host = request_data.get("host", "")
    path = request_data.get("path", "/")
    headers = request_data.get("requestHeaders") or []
    body = request_data.get("requestBody") or ""

    # Build URL
    is_tls = request_data.get("isTls", False)
    scheme = "https" if is_tls else "http"
    url = f"{scheme}://{host}{path}"

    parts = ["curl"]

    # Method (skip for default GET)
    if method and method.upper() != "GET":
        parts.append(f"-X {method}")

    # Headers
    for header in headers:
        name = header.get("name", "")
        value = header.get("value", "")
        value_escaped = value.replace("'", "'\\''")
        parts.append(f"-H '{name}: {value_escaped}'")

    # Body
    if body:
        body_escaped = body.replace("'", "'\\''")
        parts.append(f"-d '{body_escaped}'")

    # URL
    url_escaped = url.replace("'", "'\\''")
    parts.append(f"'{url_escaped}'")

    return " \\\n  ".join(parts)


def format_response(
    data: dict | list,
    compact: bool = False,
    headers_only: bool = False,
    raw: bool = False,
) -> str:
    """Format response data for agent consumption.

    Since data comes from GraphQL as plain dicts, the default mode is
    just json.dumps.  compact and headers_only provide formatted views.

    Args:
        data: A dict or list of dicts from GraphQL.
        compact: One-line-per-entry for list results.
        headers_only: Status line + headers only (no body).
        raw: Return json.dumps(data, indent=2) unchanged.

    Returns:
        Formatted string.
    """
    # ── raw / default: pretty-printed JSON ────────────────────────────
    if raw or (not compact and not headers_only):
        return json.dumps(data, indent=2)

    # ── compact mode (for lists) ─────────────────────────────────────
    if compact:
        if isinstance(data, list):
            lines = [format_entry_compact(entry) for entry in data]
            return "\n".join(lines)
        # Single entry
        return format_entry_compact(data)

    # ── headers-only mode ────────────────────────────────────────────
    if headers_only:
        # For a list, format each entry
        if isinstance(data, list):
            parts = [_format_single_headers_only(entry) for entry in data]
            return "\n\n".join(parts)
        return _format_single_headers_only(data)

    # Fallback
    return json.dumps(data, indent=2)


def _format_single_headers_only(data: dict) -> str:
    """Format a single entry as status line + headers (no body)."""
    parts = []

    # Request
    method = data.get("method", "GET")
    path = data.get("path", "/")
    host = data.get("host", "")
    querystring = data.get("query") or data.get("querystring", "")
    request_line = f"{method} {path}"
    if querystring:
        request_line += f"?{querystring}"
    parts.append(f"── Request: {host} ──")
    parts.append(request_line)
    parts.append(extract_headers(data.get("requestHeaders")))

    # Response
    status_code = data.get("statusCode", "")
    parts.append(f"── Response ──")
    parts.append(f"HTTP/1.1 {status_code}")
    parts.append(extract_headers(data.get("responseHeaders")))

    return "\n".join(parts).rstrip()


# ---------------------------------------------------------------------------
# Raw HTTP parsing + bounded views (caido_get)
# ---------------------------------------------------------------------------

HEADER_VALUE_LIMIT = 1000


def parse_raw_http(raw: Optional[str]) -> dict:
    """Split a raw HTTP message into start line, headers, and body.

    Tolerates CRLF and bare-LF line endings. Headers come back as
    ``[{name, value}]`` in wire order.
    """
    text = raw or ""
    if "\r\n\r\n" in text:
        head, _, body = text.partition("\r\n\r\n")
        line_sep = "\r\n"
    else:
        head, _, body = text.partition("\n\n")
        line_sep = "\n"
    lines = head.split(line_sep) if head else []
    headers = []
    for line in lines[1:]:
        if ":" in line:
            name, _, value = line.partition(":")
            headers.append({"name": name.strip(), "value": value.strip()})
    return {
        "start_line": lines[0] if lines else "",
        "headers": headers,
        "body": body,
    }


def _digest_cookie(value: str) -> str:
    """Request ``Cookie: a=1; b=2`` → ``[2 cookies] a, b`` (names only)."""
    names = []
    for part in value.split(";"):
        part = part.strip()
        if part:
            names.append(part.partition("=")[0].strip())
    if not names:
        return truncate_body(value, 200)
    shown = ", ".join(names[:12])
    more = f" (+{len(names) - 12} more)" if len(names) > 12 else ""
    return f"[{len(names)} cookies] {shown}{more}"


def _digest_set_cookie(value: str) -> str:
    """Response ``Set-Cookie: sid=abc; Path=/; HttpOnly`` → value redacted,
    name and attributes (flags, Path, SameSite) kept — those are the
    security-relevant parts."""
    first, sep, rest = value.partition(";")
    name, eq, _ = first.partition("=")
    if not eq:
        return truncate_body(value, 200)
    redacted = f"{name.strip()}=<redacted>"
    return f"{redacted}{sep}{rest}" if sep else redacted


def redact_headers(
    headers: Optional[list[dict]],
    redact_cookies: bool = True,
    value_limit: int = HEADER_VALUE_LIMIT,
) -> tuple[list[dict], bool]:
    """Return (possibly digested) headers + whether anything was shortened.

    With ``redact_cookies``: request ``Cookie`` values collapse to names,
    ``Set-Cookie`` values to ``name=<redacted>; attrs``. Oversized header
    values are truncated at ``value_limit`` — except cookies when
    ``redact_cookies=False``: values explicitly requested are verbatim.
    The parsed view is meant to be bounded; ``full=true`` is the verbatim
    escape hatch for everything.
    """
    out = []
    shortened = False
    for header in headers or []:
        name = header.get("name", "")
        value = header.get("value", "")
        lowered = name.lower()
        is_cookie = lowered in ("cookie", "set-cookie")
        if is_cookie and redact_cookies:
            value = _digest_cookie(value) if lowered == "cookie" else _digest_set_cookie(value)
        elif is_cookie:
            pass  # values explicitly requested — never truncated
        elif len(value) > value_limit:
            value = value[:value_limit] + f"... (+{len(value) - value_limit} chars)"
            shortened = True
        out.append({"name": name, "value": value})
    return out, shortened


def build_get_view(
    data: dict,
    redact_cookies: bool = True,
    body_limit: int = 2000,
) -> dict:
    """Build the bounded parsed view of a ``caido_get`` response.

    Keeps every identity/lookup key from ``data`` (including resolver notes
    like ``metadata_matches``) but replaces ``requestRaw``/``responseRaw``
    with parsed headers and bodies: cookie values digested (unless
    ``redact_cookies=False``), bodies truncated at ``body_limit``. The view
    is meant to be cheap enough that an agent never avoids ``caido_get`` on
    cookie-heavy or large exchanges — ``full=true`` restores the raw bytes.
    """
    req = parse_raw_http(data.get("requestRaw"))
    resp = parse_raw_http(data.get("responseRaw"))

    req_headers, req_short = redact_headers(req["headers"], redact_cookies)
    resp_headers, resp_short = redact_headers(resp["headers"], redact_cookies)
    req_body = truncate_body(req["body"], body_limit)
    resp_body = truncate_body(resp["body"], body_limit)

    notes = []
    if redact_cookies:
        notes.append(
            "cookie values digested (Cookie → names, Set-Cookie → name + flags); "
            "pass redact_cookies=false for values"
        )
    if len(req["body"]) > body_limit or len(resp["body"]) > body_limit:
        notes.append(
            f"bodies truncated at {body_limit} chars; pass full=true for verbatim raw bytes"
        )
    if req_short or resp_short:
        notes.append(
            f"header values truncated at {HEADER_VALUE_LIMIT} chars; "
            "pass full=true for verbatim raw bytes"
        )

    view = {k: v for k, v in data.items() if k not in ("requestRaw", "responseRaw")}
    view["requestHeaders"] = req_headers
    view["requestBody"] = req_body
    view["responseHeaders"] = resp_headers
    view["responseBody"] = resp_body
    view["notes"] = notes
    return view
