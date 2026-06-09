---
name: replay
description: Caido replay operations — session management, edit-and-replay pattern via Python lib/
tags: [worker, offensive]
---

# Caido Replay Operations

## When to Use This Skill

Load this skill when you need to:
- Manage replay sessions (create, rename, delete, list)
- Manage replay collections (create, list)
- Edit a request and replay it (change path, method, headers, body)
- Compose multi-step replay workflows

**For simple operations, use the plugin tools directly** — `caido_search`, `caido_get`, `caido_replay_request`, `caido_send_raw`, `caido_health`. No `execute_code` needed.

## Import Pattern

```python
import asyncio, sys
sys.path.insert(0, "/home/matt/src/hermes-caido/lib")

from replay import (
    send_raw, sessions, create_session,
    rename_session, delete_sessions, collections, create_collection,
)
from http_requests import get
```

All functions are `async`. Wrap in `asyncio.run()`:

```python
result = asyncio.run(sessions(limit=50))
```

## Session Management

### List sessions

```python
all_sessions = asyncio.run(sessions(limit=50))
# Returns: [{"id": "123", "name": "my-session"}, ...]
```

### Create named session

```python
session = asyncio.run(create_session(name="idor-test"))
# Returns: {"id": "456", "name": "idor-test"}
```

### Create session in collection

```python
session = asyncio.run(create_session(name="auth-bypass", collection_id="789"))
```

### Rename session

```python
result = asyncio.run(rename_session(session_id="456", name="new-name"))
```

### Delete sessions

```python
result = asyncio.run(delete_sessions(ids=["456", "789"]))
# Returns: {"deleted": 2, "ids": ["456", "789"]}
```

### List collections

```python
colls = asyncio.run(collections(limit=50))
# Returns: [{"id": "abc", "name": "IDOR Testing"}, ...]
```

### Create collection

```python
coll = asyncio.run(create_collection(name="Auth Bypass Tests"))
```

## Edit and Replay Pattern

The core offensive workflow: take an existing request, mutate it, replay preserving auth.

```python
async def edit_and_replay(request_id, path=None, method=None, headers=None, body=None):
    """Fetch request, apply mutations, replay."""
    req = await get(request_id=request_id)
    if "error" in req:
        return req

    raw = req.get("requestRaw", "")
    host = req.get("host", "")
    port = req.get("port", 443)
    is_tls = req.get("isTls", True)

    # Parse raw request
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

    # Apply mutations
    parts = request_line.split(" ", 2)
    if method:
        parts[0] = method
    if path:
        parts[1] = path
    request_line = " ".join(parts)

    if headers:
        for name, value in headers:
            req_headers = [h for h in req_headers if not h.lower().startswith(name.lower() + ":")]
            req_headers.append(f"{name}: {value}")

    if body is not None:
        req_body = body
        req_headers = [h for h in req_headers if not h.lower().startswith("content-length:")]
        req_headers.append(f"Content-Length: {len(body)}")

    # Reconstruct raw request
    new_raw = request_line + "\r\n"
    new_raw += "\r\n".join(req_headers) + "\r\n"
    new_raw += "\r\n" + req_body

    return await send_raw(raw_request=new_raw, host=host, port=port, tls=is_tls)

# Usage
result = asyncio.run(edit_and_replay(
    request_id="12345",
    path="/api/admin/users",
    method="POST",
    headers=[("X-Forwarded-For", "127.0.0.1")],
    body='{"role": "admin"}',
))
```

## HTTPQL Reference

Caido's query language for filtering requests. String values MUST be quoted. Integer values are NOT quoted.

**No `NOT` operator** — use negated variants: `ne`, `ncont`, `nlike`, `nregex`.

### Fields

| Namespace | Field | Type | Example |
|-----------|-------|------|---------|
| `req` | `host` | string | `req.host.cont:"api"` |
| `req` | `path` | string | `req.path.cont:"/admin"` |
| `req` | `method` | string | `req.method.eq:"POST"` |
| `req` | `query` | string | `req.query.cont:"token"` |
| `req` | `raw` | string | `req.raw.cont:"password"` |
| `req` | `port` | int | `req.port.eq:443` |
| `req` | `len` | int | `req.len.gt:1000` |
| `req` | `tls` | bool | `req.tls.eq:true` |
| `resp` | `code` | int | `resp.code.gte:400` |
| `resp` | `raw` | string | `resp.raw.cont:"error"` |
| `resp` | `len` | int | `resp.len.gt:100000` |
| `resp` | `roundtrip` | int | `resp.roundtrip.gt:5000` |
| `row` | `id` | int | `row.id.eq:12345` |
| `source` | — | special | `source:"replay"` |

### Operators

**String:** `eq`, `ne`, `cont`, `ncont`, `like`, `nlike`, `regex`, `nregex`
**Integer:** `eq`, `ne`, `gt`, `gte`, `lt`, `lte`
**Logical:** `AND`, `OR`, parentheses for grouping

### Examples

```
req.method.eq:"POST" AND resp.code.eq:200
req.host.cont:"api" OR req.path.cont:"/api/"
resp.code.gte:400 AND resp.code.lt:500
req.path.regex:"/(login|auth|signin|oauth)/"
source:"replay" OR source:"automate"
req.path.ncont:"/static" AND req.path.ncont:"/health"
```

## Pitfalls

1. **All lib/ functions are async** — always wrap in `asyncio.run()`
2. **Raw request format** — use `\r\n` line endings, not `\n`
3. **Content-Length** — update after modifying body
4. **Session create has no name field** — create then rename
5. **`startReplayTask` schema mismatch** — v0.57.0 may not accept `input` argument. If `send_raw` fails, use curl through the Caido proxy: `curl -sk -x http://127.0.0.1:8080 https://target/path`
