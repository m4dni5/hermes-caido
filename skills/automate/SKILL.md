---
name: automate
description: Caido Automate (fuzzer) — session management, payload configuration, task control, result retrieval
tags: [worker, offensive]
---

# Caido Automate

## When to Use This Skill

Load this skill when you need to:
- Create and manage automate (fuzzer) sessions
- Configure placeholders, payloads, and strategy for fuzzing
- Start, pause, resume, or cancel automate tasks
- Retrieve and filter fuzzing results
- Run targeted tests: IDOR, parameter fuzzing, auth bypass, rate limiting

**For simple operations, use the plugin tools directly** — `caido_search`, `caido_get`, `caido_findings`, `caido_health`. No `execute_code` needed.

## How to Use

Use `execute_code` (not `terminal`) to call these functions. The agent imports and calls them directly — no shell subprocess needed.

```python
# In an execute_code script:
from pathlib import Path
import sys
sys.path.insert(0, str(Path.home() / ".hermes" / "plugins" / "caido" / "lib"))
import automate
```

## Session CRUD

```python
# List sessions
sessions = automate.sessions(limit=50)

# Get session with entries and settings
session = automate.get_session(session_id="abc")
print(session["name"])
print(session["settings"]["strategy"])
print(session["entries"])

# Create session from a proxy request
result = automate.create_session(request_id="12345")
# Returns: {"id": "abc", "name": ""}

# Rename
automate.rename_session(session_id="abc", name="idor-test")

# Delete
automate.delete_session(session_id="abc")

# Duplicate (copies session with all settings)
dup = automate.duplicate_session(session_id="abc")
```

## Task Control

```python
# Start fuzzing
result = automate.start_task(session_id="abc")
# Returns: {"taskId": "1", "paused": false, "entryId": "def"}

# List running/completed tasks
tasks = automate.list_tasks(limit=50)

# Cancel
automate.cancel_task(task_id="1")

# Pause / resume
automate.pause_task(task_id="1")
automate.resume_task(task_id="1")
```

## Placeholders — Finding Values to Fuzz

Placeholders define byte ranges in the raw HTTP request that get substituted with payloads. Use the helpers in `placeholders.py` — no manual byte math.

### Approach A: Value search (find by what's there)

```python
import placeholders

# Find all occurrences of "admin" in the raw request
ranges = placeholders.find_value(raw, "admin")
# → [{"start": 142, "end": 147}]

# Target a specific occurrence
ranges = placeholders.find_value(raw, "42", occurrence=0)
```

### Approach B: Parameter-aware (find by name)

```python
# Query parameter — finds ?id=42 and returns byte range of "42"
ranges = placeholders.placeholder_for_param(raw, "id")

# JSON body — finds {"user_id": 99} and returns byte range of "99"
ranges = placeholders.placeholder_for_param(raw, "user_id")

# Form-encoded body — finds password=secret123 and returns byte range of "secret123"
ranges = placeholders.placeholder_for_param(raw, "password")

# Header value — finds Authorization: Bearer token and returns byte range of the value
ranges = placeholders.placeholder_for_header(raw, "Authorization")
```

Use Approach B first (semantic, doesn't need the current value). Fall back to Approach A for unstructured data or when you need to match a specific value.

## Payloads — What to Inject

Use `payloads.py` to configure what values get injected into placeholders. Validation happens at set time — the agent knows immediately if something doesn't match.

### Strategy determines payload structure

| Strategy | Sets needed | How they combine |
|---|---|---|
| `ALL` | 1 | Each value replaces ALL placeholders at once |
| `SEQUENTIAL` | 1 | Each value replaces placeholders one at a time |
| `MATRIX` | N (one per placeholder) | Cartesian product — every combination |
| `PARALLEL` | N (one per placeholder) | Zip — sets must have equal length |

### Simple list payloads

```python
import payloads

# ALL / SEQUENTIAL — single set
payload_sets = [["admin", "user", "test"]]
payloads.validate_payload_config("ALL", num_placeholders=2, payload_sets=payload_sets)
payload_input = payloads.build_payload_input(payload_sets)

# MATRIX — one set per placeholder, different lengths ok
payload_sets = [["admin", "user"], ["1", "2", "3"]]
payloads.validate_payload_config("MATRIX", num_placeholders=2, payload_sets=payload_sets)

# PARALLEL — one set per placeholder, same length required
payload_sets = [["admin", "user"], ["100", "200"]]
payloads.validate_payload_config("PARALLEL", num_placeholders=2, payload_sets=payload_sets)
```

### Number range payloads

```python
# Generate 1-100 in steps of 5, zero-padded to 3 digits
num_payload = payloads.build_number_payload(1, 100, increments=5, min_length=3)
```

### Preprocessors (wrap values before injection)

```python
p = payloads.build_payload_input([["test"]])[0]
payloads.add_prefix(p, "Bearer ")    # → "Bearer test"
payloads.add_suffix(p, "@example.com")  # → "test@example.com"
```

## Session Configuration (Phase 2 — coming soon)

Set payloads, strategy, concurrency, extractors via `automate.update_session()`.

## Result Retrieval (Phase 4 — coming soon)

Retrieve and filter fuzzing results with HTTPQL, sort by status/length/roundtrip.

## Quick-Start Workflow

```python
import sys, base64
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".hermes" / "plugins" / "caido" / "lib"))
import automate
import placeholders

# 1. Create session from proxy history request
session = automate.create_session(request_id="12345")
session_id = session["id"]
automate.rename_session(session_id=session_id, name="idor-test")

# 2. Get the raw request from the session
full = automate.get_session(session_id)
raw_bytes = base64.b64decode(full["raw"])
raw = raw_bytes.decode("utf-8")

# 3. Find what to fuzz
ranges = placeholders.placeholder_for_param(raw, "id")
# Or: ranges = placeholders.find_value(raw, "42")

# 4. Configure (coming in Phase 2)
# automate.update_session(session_id, settings={"placeholders": ranges, "payloads": [...], ...})

# 5. Run
result = automate.start_task(session_id=session_id)

# 6. Check results (coming in Phase 4)
# requests = automate.get_entry_requests(...)
```

## Pitfalls

1. **All functions are synchronous** — just call them, no `asyncio.run()` needed
2. **Session settings are nested** — `session["settings"]["placeholders"]`, `session["settings"]["payloads"]`, etc.
3. **`create_session` with no request_id** creates an empty session — you'll need to configure raw request manually
4. **`raw` field is base64-encoded** — it's a GraphQL Blob type. Decode with `base64.b64decode(session["raw"]).decode("utf-8")` before using placeholder helpers
5. **Placeholder byte offsets are 0-indexed** and count UTF-8 encoded bytes, not characters
6. **Tasks are tied to entries, not sessions** — `start_task` takes a session ID but creates a task per entry
7. **`cancelAutomateTask` returns `cancelledId`** not `deletedId` — different from other delete operations
8. **Pause/resume error field is `userError`** not `error` — different from most other mutations
