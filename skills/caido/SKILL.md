---
name: caido
description: Caido cookbook — shared-workspace guidance, tool map, replay & automate decisions, FUZZ slot, HTTPQL. Load when driving Caido (search, replay, automate, findings).
tags: [worker, offensive]
---

# Caido — Agent-Operator Cookbook

Work through Caido when the user should see the result; use the terminal for
private exploration.

## Caido vs Terminal

| Use Caido tools | Use terminal (curl/ffuf) |
|---|---|
| The user should see or verify the work | Independent exploration, user not watching |
| Runs that should persist in proxy history | High-volume enumeration (10k+ payloads) |
| Findings the user will review | Quick one-off probes |
| Replaying a request the user referenced | Iterating fast, no need for history |

Use `caido_export_curl` + ffuf for heavy enumeration — faster, headless,
keeps the shared history clean.

## Inject traffic through the proxy

Send traffic through the Caido proxy (commonly `127.0.0.1:8080`) so it
lands in history and becomes searchable:

```bash
curl -x http://127.0.0.1:8080 http://target.example/path
curl -sk -x http://127.0.0.1:8080 https://target.example/path   # -k for Caido's MITM CA
```

Use this to seed history with a target the user hasn't browsed yet.

## Scoping

`caido_search`/`caido_recent` filter to the active scope set by
`caido_onboard`:

- Omit `scope_id` → active scope (default)
- `scope_id=""` → full history
- `scope_id=<id>` → that scope

When a search returns empty, re-check the active scope — the traffic is
probably there outside it. `caido_onboard` reports `active_scope`.

## Tool Map

Start with `caido_onboard` (health, auth, project, scopes, recent hosts,
workspace note), then:

| Need | Tool |
|---|---|
| Find a request | `caido_search(query, compact: true)` |
| See recent traffic | `caido_recent` |
| Inspect a request/response | `caido_get(request_id)` |
| Record a vulnerability | `caido_create_finding(title, request_id, severity)` |
| Review findings | `caido_findings` |
| Remove a finding | `caido_delete_finding(finding_id)` |
| Replay once (new session) | `caido_replay(request_id, ...edits)` |
| Iterate in one session | `caido_replay(session_id, ...edits)` |
| Run a campaign (one placeholder) | `caido_automate(request_id, target, payloads, strategy)` |
| Poll a campaign + results | `caido_automate_status(session_id)` |
| Hand a request to ffuf | `caido_export_curl(request_id)` |
| Check connectivity | `caido_health` |
| Re-auth / token expiry | `caido_auth_setup` |

Every ID-taking tool accepts both the UI history-table number and the
GraphQL request id.

## Management (via lib/)

Tools only read scopes/projects/filters. When the user asks to create,
rename, update, or delete one, **do it via `lib/management.py`**:
`skill_view("caido:caido", "references/management.md")`.
After changing a scope the user wants active, re-run `caido_onboard`.

## Replay

- `caido_replay(request_id=...)` — new session, one-off replay.
- `caido_replay(session_id=...)` — edit the latest entry and resend,
  appending to the session's history. Use for iterating (auth bypass, param
  tweaks) so attempts stay grouped.

Write URL edits already encoded (`%20`, `%27`).

## Payload crafting

Write payloads to need no processing. Keep `url_encode: true` (default) for
URL/path/query fuzzing; pass `url_encode: false` and embed quoting/
termination in the values for body/JSON/header fuzzing (e.g.
`["\"admin\"", "\"user\""]`). Write values literally — `url_encode` (default)
percent-encodes for you.

For shell commands through SSRF, keep `${IFS}` in the payload list for
space-free commands.

## Automate

`caido_automate` takes one payload list (one placeholder). Strategies:

| Strategy | Sets needed | How they combine | Typical use |
|---|---|---|---|
| `ALL` | 1 | Each value replaces all placeholders | Single-parameter (default) |
| `SEQUENTIAL` | 1 | Each value replaces placeholders one at a time | Testing each position |
| `MATRIX` | N (one per placeholder) | Cartesian product | Multi-parameter enumeration |
| `PARALLEL` | N (one per placeholder) | Zip, equal length | Correlated values |

Use one payload set per placeholder for MATRIX/PARALLEL; the tool validates
this.

**FUZZ slot:** embed the literal token `FUZZ` at the target location, then
set `target` to the surrounding text. Payloads are bare data (`admin`).

```python
caido_automate(request_id="5218", target="id=42", payloads=["1","2","3","admin"], strategy="ALL")
```

**Escape hatch:** for MATRIX/PARALLEL, custom placeholder offsets,
parameter-aware placeholders, or session lifecycle, use `lib/` via
execute_code: `skill_view("caido:caido", "references/automate-lib.md")`.

## Results

`caido_automate_status` returns `status_codes`, `errors`, `highlights`
(non-2xx/errored with payloads), and `results` (`brief: false` for the full
list). Poll with `session_id` — sessions and entries persist after a run.
Cancel the task before deleting a session.

## Patterns

- **IDOR** — automate the object id in a path/query with a sequential list;
  look for 200s returning other users' data.
- **Parameter automate** — inject common parameter names as `FUZZ=1` in the
  query string.
- **Auth bypass** — automate header values (X-Forwarded-For, X-Original-URL)
  or role claims; iterate in one replay session.
- **Rate limiting** — SEQUENTIAL over the same request; watch for 429s.

## HTTPQL

Full reference: `skill_view("caido:caido", "references/httpql.md")`. Key
facts:

- Syntax `namespace.field.operator:value` — strings quoted, ints/booleans
  unquoted: `req.path.cont:"/admin"`
- Negate with `ncont` / `nlike` / `ne` / `nregex`
- Bodies/headers: search `req.raw.cont` / `resp.raw.cont` with the literal
  substring
- Status field: `resp.code`; always write the operator (`req.method.eq:"GET"`)
- `cont` is case-insensitive, `eq`/`ne` case-sensitive; `ext` needs a
  leading dot; regex is Rust-flavored
- `AND` binds tighter than `OR` — parenthesize

Verified patterns:

- Errors: `resp.code.gte:400 AND resp.code.lt:600`
- Tokens: `resp.raw.cont:"eyJ"`, `resp.raw.cont:"AKIA"`
- Missing header: `resp.raw.ncont:"Content-Security-Policy:"`
- Admin paths: `req.path.cont:"/admin" OR req.path.cont:"/wp-admin"`
- Open redirect: `req.query.cont:"redirect=" OR req.query.cont:"next="`
- Exposed files: `req.path.cont:".git" OR req.path.cont:".env"`

For more, see `rikosec/httpql-cheatsheet` on GitHub or
https://docs.caido.io/app/reference/httpql.
