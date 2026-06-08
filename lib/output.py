"""Formatting helpers for Caido CLI output."""

from __future__ import annotations

import base64
from typing import Optional


def truncate_body(body: Optional[str], max_length: int = 2000) -> str:
    """Truncate a body string to max_length chars, appending '...(truncated)' if needed.

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
    return body[:max_length] + "...(truncated)"


def extract_headers(headers: Optional[list[dict]]) -> str:
    """Format a list of {name, value} dicts into 'Name: Value\\n' string.

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
    return "\n".join(lines) + "\n"


def format_entry_compact(entry: dict) -> str:
    """Format a single request entry in compact mode: METHOD PATH STATUS LENGTH.

    Args:
        entry: A dict containing request/response data.

    Returns:
        A single-line compact representation.
    """
    method = entry.get("method", "?")
    path = entry.get("path", "/")
    status = entry.get("statusCode", "?")
    response_length = entry.get("responseLength", 0)
    return f"{method:6s} {path} {status} {response_length}"


def format_curl(request_data: dict) -> str:
    """Convert a request dict to a curl command string.

    Args:
        request_data: A dict containing request data with keys like
                      url, method, requestHeaders, requestBody, isTls.

    Returns:
        A curl command string.
    """
    url = request_data.get("url", "")
    method = request_data.get("method", "GET")
    headers = request_data.get("requestHeaders") or []
    body = request_data.get("requestBody") or ""

    parts = ["curl"]

    # Method (skip for default GET)
    if method and method.upper() != "GET":
        parts.append(f"-X {method}")

    # Headers
    for header in headers:
        name = header.get("name", "")
        value = header.get("value", "")
        # Escape single quotes in header value
        value_escaped = value.replace("'", "'\\''")
        parts.append(f"-H '{name}: {value_escaped}'")

    # Body
    if body:
        body_escaped = body.replace("'", "'\\''")
        parts.append(f"-d '{body_escaped}'")

    # URL (quote it)
    if url:
        url_escaped = url.replace("'", "'\\''")
        parts.append(f"'{url_escaped}'")

    return " \\\n  ".join(parts)


def format_response(
    data: dict,
    compact: bool = False,
    headers_only: bool = False,
    raw: bool = False,
) -> str:
    """Format response data for CLI output.

    Args:
        data: Dict with keys: id, host, method, path, url, querystring,
              requestHeaders, responseHeaders, statusCode, requestLength,
              responseLength, requestBody, responseBody, remoteAddress,
              isTls, matchedScopes.
        compact: Truncate bodies to first line, show status/length/URL.
        headers_only: Show status line + headers, no body.
        raw: Return raw request/response bytes (base64-decoded).

    Returns:
        Formatted string ready for CLI display.
    """
    # ── raw mode: decode and return raw bytes ──────────────────────────
    if raw:
        parts = []
        # Build raw request
        req_parts = []
        method = data.get("method", "GET")
        path = data.get("path", "/")
        querystring = data.get("querystring", "")
        request_line = f"{method} {path}"
        if querystring:
            request_line += f"?{querystring}"
        req_parts.append(request_line)

        req_headers = data.get("requestHeaders") or []
        for h in req_headers:
            req_parts.append(f"{h.get('name', '')}: {h.get('value', '')}")
        req_parts.append("")  # blank line after headers

        req_body = data.get("requestBody") or ""
        if req_body:
            req_parts.append(req_body)

        parts.append("\r\n".join(req_parts))

        # Build raw response
        resp_parts = []
        status_code = data.get("statusCode", "")
        resp_parts.append(f"HTTP/1.1 {status_code}")

        resp_headers = data.get("responseHeaders") or []
        for h in resp_headers:
            resp_parts.append(f"{h.get('name', '')}: {h.get('value', '')}")
        resp_parts.append("")  # blank line after headers

        resp_body = data.get("responseBody") or ""
        if resp_body:
            resp_parts.append(resp_body)

        parts.append("\r\n".join(resp_parts))

        return "\r\n\r\n".join(parts)

    # ── compact mode ───────────────────────────────────────────────────
    if compact:
        url = data.get("url", "")
        status = data.get("statusCode", "?")
        resp_len = data.get("responseLength", 0)
        resp_body = data.get("responseBody") or ""
        first_line = resp_body.split("\n", 1)[0] if resp_body else ""
        first_line = truncate_body(first_line, max_length=120)

        line = format_entry_compact(data)
        extra = f"  url={url}" if url else ""
        if first_line:
            extra += f"  body={first_line}"
        return line + extra

    # ── headers-only mode ──────────────────────────────────────────────
    if headers_only:
        parts = []

        # Request section
        method = data.get("method", "GET")
        path = data.get("path", "/")
        querystring = data.get("querystring", "")
        request_line = f"{method} {path}"
        if querystring:
            request_line += f"?{querystring}"
        parts.append(f"── Request ──")
        parts.append(request_line)
        parts.append(extract_headers(data.get("requestHeaders")))

        # Response section
        status_code = data.get("statusCode", "")
        parts.append(f"── Response ──")
        parts.append(f"HTTP/1.1 {status_code}")
        parts.append(extract_headers(data.get("responseHeaders")))

        return "\n".join(parts).rstrip()

    # ── default: full output ───────────────────────────────────────────
    parts = []

    # Metadata
    entry_id = data.get("id", "")
    host = data.get("host", "")
    remote = data.get("remoteAddress", "")
    tls = data.get("isTls", False)
    parts.append(f"── {host} ({remote}) {'[TLS]' if tls else '[plain]'} id={entry_id} ──")

    # Request
    method = data.get("method", "GET")
    path = data.get("path", "/")
    querystring = data.get("querystring", "")
    request_line = f"{method} {path}"
    if querystring:
        request_line += f"?{querystring}"
    parts.append("")
    parts.append(f"── Request ({data.get('requestLength', 0)} bytes) ──")
    parts.append(request_line)
    parts.append(extract_headers(data.get("requestHeaders")))
    req_body = data.get("requestBody") or ""
    if req_body:
        parts.append(truncate_body(req_body))

    # Response
    status_code = data.get("statusCode", "")
    parts.append("")
    parts.append(f"── Response ({data.get('responseLength', 0)} bytes) ──")
    parts.append(f"HTTP/1.1 {status_code}")
    parts.append(extract_headers(data.get("responseHeaders")))
    resp_body = data.get("responseBody") or ""
    if resp_body:
        parts.append(truncate_body(resp_body))

    return "\n".join(parts).rstrip()
