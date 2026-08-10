---
name: automate
description: Caido Automate cookbook — strategy/payload decisions, FUZZ slot pattern, pitfalls, IDOR/auth-bypass patterns. Use with caido_automate / caido_automate_status tools.
tags: [worker, offensive]
---

# Caido Automate — Fuzzing Cookbook

Caido's automate engine is called **Automate**. The `caido_automate` tool runs
a campaign in one call; this skill is the cookbook for *deciding what to automate
and how* — strategy, payloads, and the pitfalls that silently break runs.

**FUZZ** (all-caps) is the literal placeholder token embedded in the raw
request. Payloads are bare data (`admin`, not `http://host/admin`).

## When to Use

- The `caido_automate` tool returns an error and you need to understand why
- You need MATRIX/PARALLEL strategy (multiple placeholders) — `caido_automate`
  handles one placeholder; multi-slot runs go through `lib/` via execute_code
- You're automating URLs and need to know about encoding
- You want the standard patterns: IDOR, parameter automate, auth bypass

## Tool Mapping

| Need | Tool |
|---|---|
| Run a campaign (one placeholder) | `caido_automate(request_id, target, payloads, strategy)` |
| Poll a task | `caido_automate_status(task_id)` |
| Multi-placeholder / advanced config | `lib/automate` + `lib/payloads` + `lib/placeholders` via execute_code |

## Strategy × Payloads Decision Table

`caido_automate` accepts a single payload list (one placeholder). The strategy
controls how those values apply:

| Strategy | Sets needed | How they combine | Typical use |
|---|---|---|---|
| `ALL` | 1 | Each value replaces ALL placeholders at once | Single-parameter automate (default) |
| `SEQUENTIAL` | 1 | Each value replaces placeholders one at a time | Testing each position in turn |
| `MATRIX` | N (one per placeholder) | Cartesian product — every combination | Multi-parameter enumeration |
| `PARALLEL` | N (one per placeholder) | Zip — sets must have equal length | Correlated values (user=1/pass=1) |

**Rule:** ALL and SEQUENTIAL need exactly 1 payload set. MATRIX and PARALLEL
need 1 set *per placeholder*, all same length for PARALLEL. `caido_automate`
validates this before starting.

## FUZZ Slot Pattern (recommended)

Embed `FUZZ` at the exact target, then use its byte range as the placeholder.
Payloads become bare data — no preprocessors needed, URL structure stays baked
into the template.

```python
# via the tool — simplest
# caido_automate(request_id="5218", target="id=42", payloads=["1","2","3","admin"], strategy="ALL")

# via lib/ when you need the full workflow
import base64
import automate, placeholders, payloads

session = automate.create_session(request_id="5218")
session_id = session["id"]
full = automate.get_session(session_id)
raw = base64.b64decode(full["raw"]).decode("utf-8")

template = raw.replace("id=42", "id=FUZZ")
ranges = placeholders.find_value(template, "FUZZ")  # byte offsets

automate.update_session(session_id,
    raw=template,
    connection={"host": full["connection"]["host"], "port": full["connection"]["port"], "isTLS": full["connection"]["isTLS"]},
    settings={
        "placeholders": ranges,
        "payloads": payloads.build_payload_input([["1", "2", "3", "admin"]]),
        "strategy": "ALL",
    })
result = automate.start_task(session_id)
```

## Patterns

- **IDOR** — automate the object id in a path or query (`/users/{id}`, `?user_id=`)
  with a small sequential list; look for 200s returning other users' data.
- **Parameter automate** — discover hidden parameters with a wordlist of common
  names injected as `FUZZ=1` in the query string.
- **Auth bypass** — automate header values (X-Forwarded-For, X-Original-URL) or
  role claims in a JSON body; check status-code changes.
- **Rate limiting** — SEQUENTIAL over the same request; watch for 429s.

## Pitfalls

1. **Raw is base64** — `session["raw"]` is a GraphQL Blob; decode before
   placeholder helpers. The tool does this for you.
2. **Byte offsets are UTF-8 bytes, not characters** — multi-byte content
   (non-ASCII) produces different offsets. `placeholders.find_value` handles
   this; don't hand-compute.
3. **URL-encode payloads when automating inside URLs** — Caido's hosted-file
   payloads don't auto-encode. Use the `urlEncode` preprocessor or pre-encode
   your wordlist. `${IFS}` bypasses space restrictions in shell commands
   passed through SSRF.
4. **Update requires connection dict** — `update_session` needs the full
   connection info even when only changing settings; always fetch the session
   first (the tool does this internally).
5. **Tasks are tied to entries, not sessions** — `start_task` takes a session
   ID but creates a task per entry.
6. **MATRIX/PARALLEL need N sets** — passing one flat list to a multi-slot
   session fails validation with a clear message. Use the tool for single-slot,
   execute_code for multi-slot.
7. **`cancelAutomateTask` returns `cancelledId`**, not `deletedId`; pause/resume
   errors come back in `userError`, not `error`.
8. **Deleting a session with a task fails** — cancel the task first
   (`cancel_task`), then delete the session.

## HTTPQL Quick Reference (for result filtering)

String fields use quoted values; integers unquoted. No `NOT` — use `ne`,
`ncont`, `nlike`, `nregex`. Common: `req.host.cont:"api"`,
`req.path.cont:"/admin"`, `req.method.eq:"POST"`, `resp.code.gte:400`,
`resp.len.gt:100000`, `resp.roundtrip.gt:5000`.
