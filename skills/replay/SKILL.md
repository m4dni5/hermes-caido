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

**For simple operations, use the plugin tools directly** — `caido_search`, `caido_get`, `caido_findings`, `caido_health`. No `execute_code` needed.

## Import Pattern

```python
import asyncio, base64, sys
sys.path.insert(0, "/home/matt/src/hermes-caido/lib")

from replay import (
    replay, sessions, create_session, start_replay_task,
    rename_session, delete_sessions, collections, create_collection,
)
from http_requests import get
from client import graphql
```

All functions are `async`. Wrap in `asyncio.run()`:

```python
result = asyncio.run(sessions(limit=50))
```

## Replay Workflow (v0.57.0)

The Caido v0.57.0 replay system uses sessions with entries. Each session contains one or more entries (requests). The workflow:

1. **Create session from request** — `createSession(request_id="123")` seeds session with request
2. **Rename session** — `renameSession(session_id, "my-test")`
3. **Start replay task** — `startReplayTask(session_id)` replays the entry
4. **Get results** — check HTTP history for the replayed request

### Quick replay (one-liner)

```python
result = asyncio.run(replay(request_id="123"))
# Returns: {"status": "DONE", "sessionId": "5", "taskId": "1"}
```

### Step-by-step replay

```python
# Step 1: Create session from request
session = asyncio.run(create_session(request_id="123"))
session_id = session["id"]

# Step 2: Rename
asyncio.run(rename_session(session_id, "idor-test"))

# Step 3: Start replay
result = asyncio.run(start_replay_task(session_id))
```

## Edit and Replay Pattern

To modify a request before replaying:

1. Get the request raw bytes
2. Modify the raw HTTP request
3. Create session with the modified request via `updateReplayEntryDraft`

### Get session entries

```python
q = """
query {
    replaySession(id: "SESSION_ID") {
        id name
        ... on ReplaySessionHttp {
            entries(first: 10) {
                edges {
                    node {
                        id
                        ... on ReplayEntryHttp {
                            raw
                            connection { host port isTLS }
                            request { id method path host }
                        }
                    }
                }
            }
        }
    }
}
data = asyncio.run(graphql(q))
entries = data["replaySession"]["entries"]["edges"]
entry_id = entries[0]["node"]["id"]
raw_b64 = entries[0]["node"]["raw"]
```

### Edit entry draft

```python
# Decode current request
raw_bytes = base64.b64decode(raw_b64).decode("utf-8")

# Modify it (e.g., change path)
lines = raw_bytes.split("\r\n")
parts = lines[0].split(" ", 2)
parts[1] = "/api/admin/users"
lines[0] = " ".join(parts)
modified_raw = "\r\n".join(lines)

# Update the draft
edit_mutation = """
mutation UpdateReplayEntryDraft($id: ID!, $input: UpdateReplayEntryDraftInput!) {
    updateReplayEntryDraft(id: $id, input: $input) {
        entry { id }
    }
}
"""
asyncio.run(graphql(edit_mutation, {
    "id": entry_id,
    "input": {
        "http": {
            "raw": base64.b64encode(modified_raw.encode()).decode(),
            "connection": {"host": "target.com", "port": 443, "isTLS": True},
            "settings": {"placeholders": []},
            "editorState": base64.b64encode(b"{}").decode(),
        }
    }
}))

# Start replay
result = asyncio.run(start_replay_task(session_id))
```

## Session Management

### List sessions

```python
all_sessions = asyncio.run(sessions(limit=50))
# Returns: [{"id": "123", "name": "my-session"}, ...]
```

### Create session (without request)

```python
session = asyncio.run(create_session(name="empty-session"))
```

### Create session with request

```python
session = asyncio.run(create_session(name="idor-test", request_id="123"))
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

1. **All lib/ functions are async** — always wrap in `asyncio.run()`
2. **Raw request format** — use `\r\n` line endings, not `\n`
3. **Content-Length** — update after modifying body
4. **Session create has no name field** — create then rename
5. **Entry raw is base64-encoded** — decode before editing, re-encode after
6. **Entries are ReplayEntry interface** — use `... on ReplayEntryHttp` inline fragment
7. **No `send_raw` mutation** — v0.57.0 doesn't support sending arbitrary raw requests via GraphQL. Use `createSession` + `updateReplayEntryDraft` + `startReplayTask` instead
