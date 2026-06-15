---
name: replay
description: Caido replay operations — session management, edit-and-replay pattern via Python lib/
tags: [worker, offensive]
---

# Caido Replay Operations

## When to Use This Skill

Load this skill when you need to:
- Replay requests from HTTP history
- Edit requests and replay them (change path, method, headers, body)
- Manage replay sessions (create, rename, delete, list)
- Manage replay collections (create, list)
- Send custom curl commands and want them captured in Caido

**For simple operations, use the plugin tools directly** — `caido_search`, `caido_get`, `caido_findings`, `caido_health`. No `execute_code` needed.

## Routing curl Through the Caido Proxy

When you need to use `curl` directly (SSRF payloads, custom requests, testing exploits), **always route through the Caido proxy** so the traffic is captured in proxy history:

```bash
curl --proxy http://127.0.0.1:8080 -X POST "http://target/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "param=value"
```

This ensures:
- Requests appear in `caido_search` and `caido_recent`
- Responses can be inspected with `caido_get`
- Findings can be linked to specific requests
- The full request/response is logged for later analysis

The proxy URL is the same as `CAIDO_URL` (the Caido instance URL). If the agent doesn't know the proxy URL, it can check with `caido_setup` (action: status) or read from `CAIDO_URL` in `~/.hermes/.env`.

**Without the proxy flag, curl traffic is invisible to Caido.**

## How to Use

Use `execute_code` (not `terminal`) to call these functions. The agent imports and calls them directly — no shell subprocess needed.

```python
# In an execute_code script:
from pathlib import Path
import sys
sys.path.insert(0, str(Path.home() / ".hermes" / "plugins" / "caido" / "lib"))
import replay
```

## Quick Replay

```python
result = replay.replay(request_id="123")
# Returns: {"status": "DONE", "sessionId": "5", "taskId": "1"}
```

## Edit and Replay

One function call — fetches request, applies mutations, creates session, updates draft, replays.

```python
result = replay.replay_with_edit(
    request_id="123",
    path="/api/admin/users",
    method="POST",
    headers=[("X-Forwarded-For", "127.0.0.1")],
    body='{"role": "admin"}',
    session_name="priv-esc-test",
)
# Returns: {"status": "DONE", "sessionId": "5", "taskId": "1", "mutations": ["path: /api -> /api/admin/users", "method: GET -> POST", ...]}
```

All parameters are optional — only apply the mutations you need:

```python
# Just change the path
result = replay.replay_with_edit(request_id="123", path="/api/v2/users")

# Just add a header
result = replay.replay_with_edit(request_id="123", headers=[("Authorization", "Bearer xxx")])

# Just change the body
result = replay.replay_with_edit(request_id="123", body='{"admin": true}')
```

## Session Management

```python
# List sessions
replay.sessions(limit=50)

# Get session with entries
session = replay.get_session(session_id="5")
print(session["entries"])

# Create session from request
replay.create_session(name="my-test", request_id="123")

# Rename
replay.rename_session(session_id="5", "new-name")

# Delete
replay.delete_sessions(ids=["5", "6"])

# Move to collection
replay.move_session(session_id="5", collection_id="1")
```

## Collections

```python
replay.collections(limit=50)
replay.create_collection(name="IDOR Tests")
```

## Entry Manipulation

For advanced workflows where you need to inspect or edit entries directly:

```python
# Get entries from a session
entries = replay.get_session_entries(session_id="5")
entry_id = entries[0]["id"]
raw = entries[0]["raw"]  # Decoded HTTP request string

# Get a specific entry
entry = replay.get_entry(entry_id="7")

# Update entry draft directly
replay.update_entry_draft(
    entry_id="7",
    raw="GET /api/admin HTTP/1.1\r\nHost: target.com\r\n\r\n",
    host="target.com",
    port=443,
    is_tls=True,
)

# Clear draft (revert to original)
replay.clear_entry_draft(entry_id="7")

# Start replay on the session
replay.start_replay_task(session_id="5")
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

## Pitfalls

1. **All functions are synchronous** — just call them, no `asyncio.run()` needed
2. **Raw request format** — use `\r\n` line endings, not `\n`
3. **Content-Length** — `replay_with_edit` updates this automatically when you set `body`
4. **Session create has no name field** — create then rename (happens automatically)
5. **Entry raw is decoded** — lib/ handles base64 encode/decode transparently
