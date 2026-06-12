"""Placeholder helpers for Caido Automate.

Calculate byte offsets in raw HTTP requests for use as automate placeholders.
Two approaches:

A) find_value(raw, value) — grep-style, find any value by its bytes
B) placeholder_for_param / placeholder_for_header — semantic, find by name

All functions work on raw HTTP request strings (with \\r\\n line endings).
Returns lists of {"start": int, "end": int} dicts (byte offsets, 0-indexed).
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, unquote


def _byte_offset(raw: str, char_offset: int) -> int:
    """Convert a character offset to a byte offset in the raw string."""
    return len(raw[:char_offset].encode("utf-8"))


# ---------------------------------------------------------------------------
# Approach A: Value search
# ---------------------------------------------------------------------------


def find_value(raw: str, value: str, occurrence: int | None = None) -> list[dict]:
    """Find all byte ranges where `value` appears in the raw request.

    Args:
        raw: The raw HTTP request string.
        value: The string value to search for.
        occurrence: If set, return only the Nth occurrence (0-indexed).

    Returns:
        List of {"start": N, "end": N} dicts with byte offsets.
        Empty list if value not found.
    """
    results = []
    search_from = 0
    while True:
        idx = raw.find(value, search_from)
        if idx == -1:
            break
        start = _byte_offset(raw, idx)
        end = start + len(value.encode("utf-8"))
        results.append({"start": start, "end": end})
        search_from = idx + 1

    if occurrence is not None:
        if 0 <= occurrence < len(results):
            return [results[occurrence]]
        return []

    return results


# ---------------------------------------------------------------------------
# Approach B: Semantic placeholders
# ---------------------------------------------------------------------------


def _split_request(raw: str) -> tuple[str, list[str], str]:
    """Split raw HTTP request into request_line, header_lines, body.

    Handles both \\r\\n and \\n line endings.
    """
    if "\r\n" in raw:
        parts = raw.split("\r\n")
    else:
        parts = raw.split("\n")

    request_line = parts[0]
    header_lines = []
    body = ""
    in_body = False

    for line in parts[1:]:
        if in_body:
            body += line + "\n"
            continue
        if line.strip() == "":
            in_body = True
            continue
        header_lines.append(line)

    return request_line, header_lines, body.rstrip("\n")


def _find_header_value_range(raw: str, header_name: str) -> dict | None:
    """Find the byte range of a header's value in the raw request.

    Returns {"start": N, "end": N} or None if not found.
    """
    header_lower = header_name.lower()

    # Search line by line to handle \r\n properly
    if "\r\n" in raw:
        lines = raw.split("\r\n")
        separator = "\r\n"
    else:
        lines = raw.split("\n")
        separator = "\n"

    offset = 0
    for line in lines:
        line_end = offset + len(line.encode("utf-8"))
        if ":" in line:
            name, _, value_part = line.partition(":")
            if name.strip().lower() == header_lower:
                # Value starts after "Name: "
                value_start_char = offset + len(name.encode("utf-8")) + len(": ".encode("utf-8"))
                # In raw bytes, "Name: " is name_bytes + 2 (": ")
                value_start = len(raw[:raw.index(line) + len(name) + 2].encode("utf-8"))
                value_end = value_start + len(value_part.strip().encode("utf-8"))
                return {"start": value_start, "end": value_end}
        # Move past this line + separator
        offset = line_end + len(separator.encode("utf-8"))

    return None


def placeholder_for_header(raw: str, header_name: str) -> list[dict]:
    """Find the byte range of a header's value.

    Args:
        raw: The raw HTTP request string.
        header_name: The header name (case-insensitive).

    Returns:
        List with one {"start": N, "end": N} dict, or empty list if not found.
    """
    result = _find_header_value_range(raw, header_name)
    return [result] if result else []


def _get_query_string(raw: str) -> tuple[str, int]:
    """Extract the query string from the request line.

    Returns (query_string, byte_offset_of_query_start_in_raw).
    """
    request_line = raw.split("\r\n")[0] if "\r\n" in raw else raw.split("\n")[0]
    # GET /path?query HTTP/1.1
    parts = request_line.split(" ")
    if len(parts) < 2:
        return "", 0

    path = parts[1]
    if "?" not in path:
        return "", 0

    query = path.split("?", 1)[1]
    # Byte offset of the query string in the raw request
    query_char_idx = raw.index("?")
    query_byte_start = _byte_offset(raw, query_char_idx + 1)
    return query, query_byte_start


def _get_body_and_offset(raw: str) -> tuple[str, int]:
    """Get the request body and its byte offset in the raw request.

    Returns (body, byte_offset_of_body_start).
    """
    if "\r\n\r\n" in raw:
        separator = "\r\n\r\n"
    elif "\n\n" in raw:
        separator = "\n\n"
    else:
        return "", 0

    body_start_char = raw.index(separator) + len(separator)
    body = raw[body_start_char:]
    body_byte_start = _byte_offset(raw, body_start_char)
    return body, body_byte_start


def placeholder_for_param(raw: str, param_name: str) -> list[dict]:
    """Find the byte range of a parameter's value in the request.

    Searches in order: query string, JSON body, form-encoded body.

    Args:
        raw: The raw HTTP request string.
        param_name: The parameter name to find.

    Returns:
        List with one {"start": N, "end": N} dict, or empty list if not found.
    """
    # 1. Query string
    query, query_byte_start = _get_query_string(raw)
    if query:
        params = parse_qs(query, keep_blank_values=True)
        if param_name in params:
            value = params[param_name][0]
            # Find the value's position in the raw query string
            # Query is param=value&param2=value2
            search_str = f"{param_name}="
            idx = query.find(search_str)
            if idx != -1:
                value_char_in_query = idx + len(search_str)
                value_byte_in_query = len(query[:value_char_in_query].encode("utf-8"))
                value_bytes = len(value.encode("utf-8"))
                return [{"start": query_byte_start + value_byte_in_query,
                         "end": query_byte_start + value_byte_in_query + value_bytes}]

    # 2. JSON body
    body, body_byte_start = _get_body_and_offset(raw)
    if body and body.strip().startswith("{"):
        try:
            data = json.loads(body)
            if param_name in data:
                value = str(data[param_name])
                # Find the value's position in the raw body JSON
                # Look for "param_name": "value" or "param_name": value
                search_patterns = [
                    f'"{param_name}": "{value}"',
                    f'"{param_name}": "{value}',
                    f'"{param_name}": {value}',
                ]
                for pattern in search_patterns:
                    idx = body.find(pattern)
                    if idx != -1:
                        # Find the value within the pattern
                        value_in_pattern = pattern.rfind(value)
                        value_char_in_body = idx + value_in_pattern
                        value_byte_in_body = len(body[:value_char_in_body].encode("utf-8"))
                        value_bytes = len(value.encode("utf-8"))
                        return [{"start": body_byte_start + value_byte_in_body,
                                 "end": body_byte_start + value_byte_in_body + value_bytes}]
        except (json.JSONDecodeError, KeyError):
            pass

    # 3. Form-encoded body
    if body and "=" in body and not body.strip().startswith("{"):
        params = parse_qs(body, keep_blank_values=True)
        if param_name in params:
            value = params[param_name][0]
            search_str = f"{param_name}="
            idx = body.find(search_str)
            if idx != -1:
                value_char_in_body = idx + len(search_str)
                value_byte_in_body = len(body[:value_char_in_body].encode("utf-8"))
                value_bytes = len(value.encode("utf-8"))
                return [{"start": body_byte_start + value_byte_in_body,
                         "end": body_byte_start + value_byte_in_body + value_bytes}]

    return []
