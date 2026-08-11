---
name: caido
description: Caido cookbook — shared-workspace guidance, tool map, replay & automate decisions, FUZZ slot, patterns, pitfalls, HTTPQL. Load when driving Caido (search, replay, automate, findings).
tags: [worker, offensive]
---

# Caido — Agent-Operator Cookbook

Caido is the proxy in the user's workspace. This skill is the judgment layer:
*when to use Caido vs the terminal*, *which tool to reach for*, and *the
pitfalls that silently break sessions and runs*. Tool descriptions carry the
mechanics; this carries the decisions.

**FUZZ** (all-caps) is the literal placeholder token embedded in the raw
request. Payloads are bare data (`admin`, not `http://host/admin`).

## Caido vs Terminal — the shared workspace

**Caido is the shared workspace.** Traffic you replay, automate runs, and
findings you create appear in the Caido UI the user is watching. The plugin's
value is *collaboration*: the user sees what you're doing and can click through,
verify, and build on it. The command line is for work the user doesn't need to
watch.

| Use Caido tools | Use terminal (curl/ffuf) |
|---|---|
| The user should see or verify the work | Independent exploration, user not watching |
| Runs that should persist in proxy history | High-volume enumeration (10k+ payloads) |
| Findings the user will review | Quick one-off probes |
| Replaying a request the user referenced | Iterating fast, no need for history |

Rule of thumb: **if the user would benefit from seeing it in the Caido UI, do
it in Caido. If it's your own private probing, use the terminal.** Prefer
`caido_export_curl` + ffuf for heavy enumeration — it's faster, headless, and
keeps the shared history clean.

## Injecting traffic through the Caido proxy

The Caido proxy listens on the instance's proxy port (commonly
`127.0.0.1:8080`). You can send traffic through it from the terminal — it
lands in proxy history and becomes visible to `caido_search`/`caido_recent`:

```bash
# Plain HTTP
curl -x http://127.0.0.1:8080 http://target.example/path

# HTTPS — Caido MITMs TLS with its own CA, so use -k (or trust the CA)
curl -sk -x http://127.0.0.1:8080 https://target.example/path
```

This is the shared-workspace loop: **terminal injects → proxy captures → agent
searches → replay/automate on it.** Use it to seed history with a target the
user hasn't browsed yet, then run automate against the captured request.

## Scoping — how search/recent filter

`caido_onboard` sets an **active scope** (module state) by matching recent
hosts against scope allowlists. `caido_search` and `caido_recent` filter to
that scope by default — traffic outside it (e.g. curl-injected hosts not in
the scope) is invisible unless you opt out:

- **Omit `scope_id`** → filtered by the active scope (the common case)
- **`scope_id=""`** → no scope filter, full history
- **`scope_id=<id>`** → filter by a specific scope

If a search comes back empty but you expected traffic, check the active scope
first — the request is probably there but outside it. `caido_onboard` reports
`active_scope` so you always know the current filter.

## Scope & project lifecycle (via lib/)

Scope and project creation/editing are **not tool surface** — but if the user
asks you to create, rename, update, or delete a scope or project, **do it —
don't push them to the UI.** The full CRUD (scopes, projects, filters,
environments, hosted files) lives in `lib/management.py`. Verified usage:
load `skill_view("caido:caido", "references/management.md")`.

After creating/editing a scope the user wants active, re-run `caido_onboard`
(or call `set_active_scope` from `lib/http_requests.py`) so search/recent pick
up the change.

## Tool Map

Start every Caido session with `caido_onboard` — it returns health, auth,
project, scopes, recent hosts, and a workspace note. Then:

| Need | Tool |
|---|---|
| Orient + set active scope | `caido_onboard` (first call of a session) |
| Find a request in history | `caido_search(query, compact: true)` |
| See what the proxy just captured | `caido_recent` |
| Inspect a request/response pair | `caido_get(request_id)` — accepts UI numbers |
| Record a vulnerability | `caido_create_finding(title, request_id, severity)` |
| Review recorded findings | `caido_findings` |
| Remove a finding | `caido_delete_finding(finding_id)` — false positives, test artifacts |
| Replay once (new session) | `caido_replay(request_id, ...edits)` |
| Iterate in one session | `caido_replay(session_id, ...edits)` — appends to history |
| Run a campaign (one placeholder) | `caido_automate(request_id, target, payloads, strategy)` |
| Poll a campaign + results | `caido_automate_status(session_id)` |
| Hand a request to ffuf | `caido_export_curl(request_id)` then run the curl in ffuf |
| Check connectivity | `caido_health` |
| Re-auth / token expiry | `caido_auth_setup` |

**Request IDs are dual-namespace.** The Caido UI history table shows
`metadata.id` (a group key); tools return the GraphQL `Request.id`. Every
ID-taking tool (`caido_get`, `caido_replay`, `caido_automate`,
`caido_export_curl`, `caido_create_finding`) accepts either — a number quoted
from the UI resolves automatically.

## Replay: one-shot vs iteration

`caido_replay` has two modes (see its description):

- **`request_id` mode** — creates a new session and replays once. Right for a
  one-off replay the user referenced.
- **`session_id` mode** — edits the session's latest entry and resends,
  appending a new entry to the same session's history. Use for iterating on
  the same request (auth bypass attempts, parameter tweaks) so all attempts
  stay grouped in the Replay tab's history drop-down.

**Replay sessions accumulate entries** — each send appends one. The UI shows
the latest with a History drop-down/arrows for previous ones.

**Replay edits are literal — there is no url_encode option.** `caido_replay`
passes method/path/header/body edits verbatim into the raw request. If you put
a space or reserved character in a path/query edit (`?uid=admin' or '1'='1`),
the request line is malformed and the server returns 400 with empty
method/path in history. Encode URL edits yourself (`%20`, `%27`, etc.) — unlike
`caido_automate`, replay will not do it for you.

## Preprocessors vs. payload crafting

Caido supports preprocessors (prefix, suffix, urlEncode, custom workflows), but
the tool deliberately exposes only the one that matters most: **url_encode**
(default true, matching the Caido UI default — payloads are percent-encoded
before injection with the UI's charset `:/?#[]{}@$&+ ,;=%<>`, so spaces and
reserved chars don't break the request line).

Rule of thumb: **write payloads to not need processing.**

- URL/path/query fuzzing → keep `url_encode: true` (default). A payload like
  `admin or 1=1` is sent as `admin%20or%201%3D1` and works.
- Body/JSON/header fuzzing → pass `url_encode: false` and embed the required
  quoting/termination directly in the payload values: `["\"admin\"", "\"user\""]`
  instead of `["admin", "user"]` with a quote preprocessor.
- Anything else (prefix/suffix/custom workflows) → generate the transformed
  payload list yourself. It's just as easy, and the status tool then shows
  exactly what was sent — no invisible transform layer.

## Automate: strategy & the FUZZ slot

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

**FUZZ slot pattern (recommended):** embed `FUZZ` at the exact target, then
use its byte range as the placeholder. Payloads become bare data — URL
structure stays baked into the template.

```python
# via the tool — simplest (one placeholder, one payload list)
caido_automate(request_id="5218", target="id=42", payloads=["1","2","3","admin"], strategy="ALL")
```

For multi-placeholder / advanced config (MATRIX, PARALLEL, custom
placeholders, raw session editing) the tool doesn't go deep enough — use
`lib/` via execute_code. Verified workflow:
`skill_view("caido:caido", "references/automate-lib.md")`.

## Results — what the run produced

`caido_automate_status` returns the run's outcomes, not just "started":

- **`status_codes`** — distribution across the run (e.g. `{"200": 3, "403": 2}`),
  with `error/no-response` for requests that timed out or failed
- **`errors`** — count by error type (e.g. `{"Timeout": 5}`)
- **`highlights`** — non-2xx / errored results with their payload values
- **`results`** (with `brief: false`) — full list: payload → request → status

**Use `session_id` for polling.** `caido_automate` returns three handles —
`session_id`, `task_id`, `entry_id` — but only sessions (and their entries)
persist after a run finishes. Tasks drop off the recent list, so `task_id`
works only while the run is visible. Pass `session_id` (or `entry_id`) to
`caido_automate_status` to poll both in-progress and completed runs with one
handle. If the target is slow, results may show `error/no-response` with a
`Timeout` error — that's the fuzzer's own timeout, not a plugin bug.

## Patterns

- **IDOR** — automate the object id in a path or query (`/users/{id}`, `?user_id=`)
  with a small sequential list; look for 200s returning other users' data.
- **Parameter automate** — discover hidden parameters with a wordlist of common
  names injected as `FUZZ=1` in the query string.
- **Auth bypass** — automate header values (X-Forwarded-For, X-Original-URL) or
  role claims in a JSON body; check status-code changes. Iterate in one replay
  session via `caido_replay(session_id=...)`.
- **Rate limiting** — SEQUENTIAL over the same request; watch for 429s.

## Pitfalls

1. **Raw is base64** — `session["raw"]` is a GraphQL Blob; decode before
   placeholder helpers. The tool does this for you.
2. **Byte offsets are UTF-8 bytes, not characters** — multi-byte content
   (non-ASCII) produces different offsets. `placeholders.find_value` handles
   this; don't hand-compute.
3. **URL-encoding is on by default** — `caido_automate` percent-encodes
   payloads with the UI's charset (spaces/reserved chars → `%XX`), which is
   what you want inside URLs. Set `url_encode: false` only when fuzzing
   bodies/JSON/headers where literal values matter. If you hand-encode values
   AND leave url_encode on, you'll double-encode (`%2520`).
4. **Shell injection inside URLs** — when automating shell commands through
   SSRF/param injection, spaces may be stripped by the backend even when
   URL-encoded. `${IFS}` (no spaces) bypasses space restrictions; keep it in
   the payload list.
5. **Update requires connection dict** — `update_session` needs the full
   connection info even when only changing settings; always fetch the session
   first (the tool does this internally).
6. **Tasks are tied to entries, not sessions** — `start_task` takes a session
   ID but creates a task per entry.
7. **MATRIX/PARALLEL need N sets** — passing one flat list to a multi-slot
   session fails validation with a clear message. Use the tool for single-slot,
   execute_code for multi-slot.
8. **`cancelAutomateTask` returns `cancelledId`**, not `deletedId`; pause/resume
   errors come back in `userError`, not `error`.
9. **Deleting a session with a task fails** — cancel the task first
   (`cancel_task`), then delete the session.
10. **Completed tasks leave the recent list** — poll with `session_id` (or
    `entry_id`), not `task_id`, after the run finishes (see "Results" above);
    sessions and entries persist with all results.
11. **Replay sessions accumulate entries** — each `startReplayTask` appends a
    new entry to the session's history. Use `caido_replay(session_id=...)`
    to iterate (auth bypass, param tweaks) and keep attempts grouped; the UI
    shows the latest with a History drop-down/arrows for previous ones.
12. **Replay edits are literal; automate payloads are encoded** — the two
    tools have opposite defaults. See "Replay: one-shot vs iteration" above:
    `caido_replay` passes edits verbatim (encode URL edits yourself),
    `caido_automate` URL-encodes payloads by default.

## HTTPQL — the caido_search query language

Syntax: `namespace.field.operator:value` (e.g. `req.path.cont:"/admin"`).
String values are quoted; integers and booleans are not. Full field and
operator tables, plus verified patterns: load the reference
`skill_view("caido:caido", "references/httpql.md")`.

Key facts (verified against the live 0.57.x schema):

1. **Negate with `ncont` / `nlike` / `ne` / `nregex`** — there is no `NOT`.
2. **Bodies and headers live in `raw`** — search them with `req.raw.cont` /
   `resp.raw.cont` (`resp.raw.cont:"error"` for stack traces,
   `resp.raw.cont:"Set-Cookie:"` for cookies).
3. **Status code is `resp.code`** — and always write the operator:
   `req.method.eq:"GET"` (bare `req.method:"GET"` is invalid).
4. **`cont` is case-insensitive; `eq`/`ne` are case-sensitive**; `ext`
   needs a leading dot (`req.ext.eq:".js"`); regex is Rust-flavored.

`AND` binds tighter than `OR` — parenthesize (`(req.method.eq:"POST" OR
req.method.eq:"PUT") AND resp.code.gte:400`).

Verified patterns:

- Errors: `resp.code.gte:400 AND resp.code.lt:600`
- Slow responses: `resp.roundtrip.gt:5000`; large: `resp.len.gt:100000`
- Tokens: `resp.raw.cont:"eyJ"` (JWT), `resp.raw.cont:"AKIA"` (AWS key)
- Missing security header: `resp.raw.ncont:"Content-Security-Policy:"`
- Admin paths: `req.path.cont:"/admin" OR req.path.cont:"/wp-admin"`
- Open redirect: `req.query.cont:"redirect=" OR req.query.cont:"next="`
- Exposed files: `req.path.cont:".git" OR req.path.cont:".env"`
- Regex on paths: `req.path.regex:"/v[0-9]"`

For more patterns, see `rikosec/httpql-cheatsheet` on GitHub (a
browserable query library) or the official reference at
https://docs.caido.io/app/reference/httpql.
