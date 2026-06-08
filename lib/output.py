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

    Takes a dict with id, method, host, path, statusCode, createdAt.

    Returns:
        A single line: "{id} {method} {host}{path} [{statusCode}] {createdAt}"
    """
    entry_id = entry.get("id", "?")
    method = entry.get("method", "?")
    host = entry.get("host", "")
    path = entry.get("path", "/")
    status = entry.get("statusCode", "?")
    created = entry.get("createdAt", "")
    return f"{entry_id} {method} {host}{path} [{status}] {created}"


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
    querystring = data.get("querystring", "")
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
