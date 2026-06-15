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

**When testing exploit payloads manually, route curl through the Caido proxy** — see `caido:replay` for the `--proxy` pattern. This ensures all traffic is captured in proxy history.

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

### Recommended: FUZZ slot pattern

Modify the raw request to embed `FUZZ` at the target location, then find its byte range. Payloads become bare data — no preprocessors needed.

```python
import placeholders

# 1. Decode the raw request
raw = base64.b64decode(session["raw"]).decode("utf-8")

# 2. Substitute the target with FUZZ
template = raw.replace("truckapi.htb/?id%3DFusionExpress03", "127.0.0.1/FUZZ/")

# 3. Find where FUZZ landed
ranges = placeholders.find_value(template, "FUZZ")
# → [{"start": 399, "end": 403}]

# 4. Use template as the new raw, ranges as the placeholder
# Payloads are just bare paths: ["admin", "js", "css", "login", ...]
```

This is better than placing a placeholder on the entire value because:
- Payloads are bare data (`admin`) not full URLs (`http://127.0.0.1/admin`)
- No URL-encoding issues — the URL structure is baked into the template
- Smaller byte range — less chance of breaking the request
- No preprocessors needed

### Approach A: Value search (find by what's there)

```python
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

# Header value — finds Authorization: Bearer *** and returns byte range of the value
ranges = placeholders.placeholder_for_header(raw, "Authorization")
```

Use the FUZZ slot pattern first (most ergonomic). Fall back to Approach B (semantic) when you know the parameter name. Fall back to Approach A (value search) for unstructured data.

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
raw = base64.b64decode(full["raw"]).decode("utf-8")

# 3. Craft the template — embed FUZZ at the target
template = raw.replace("id=42", "id=FUZZ")

# 4. Find the FUZZ byte range
ranges = placeholders.find_value(template, "FUZZ")

# 5. Update session with the template and placeholder
connection = full["connection"]
automate.update_session(session_id,
    raw=template,
    connection={"host": connection["host"], "port": connection["port"], "isTLS": connection["isTLS"]},
    settings={
        "placeholders": ranges,
        "payloads": payloads.build_payload_input([["1", "2", "3", "admin"]]),
        "strategy": "ALL",
        ...  # see payloads section
    })

# 6. Run
result = automate.start_task(session_id=session_id)
```

## Pitfalls

1. **All functions are synchronous** — just call them, no `asyncio.run()` needed
2. **Session settings are nested** — `session["settings"]["placeholders"]`, `session["settings"]["payloads"]`, etc.
3. **`create_session` with no request_id** creates an empty session — you'll need to configure raw request manually
4. **`raw` field is base64-encoded** — it's a GraphQL Blob type. Decode with `base64.b64decode(session["raw"]).decode("utf-8")` before using placeholder helpers
5. **Placeholder byte offsets are 0-indexed** and count UTF-8 encoded bytes, not characters
6. **URL-encode payload values** when fuzzing inside URLs — Caido's hosted file payloads don't auto-encode. Use the `urlEncode` preprocessor or pre-encode your wordlist.
7. **FUZZ slot pattern beats whole-value placeholders** — embed `FUZZ` in the raw template, fuzz the smallest variable part
8. **Tasks are tied to entries, not sessions** — `start_task` takes a session ID but creates a task per entry
9. **`cancelAutomateTask` returns `cancelledId`** not `deletedId` — different from other delete operations
10. **Pause/resume error field is `userError`** not `error` — different from most other mutations
