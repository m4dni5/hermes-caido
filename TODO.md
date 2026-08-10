# TODO — hermes-caido

> Last reviewed: 2026-08-10
> Caido latest: **v0.57.1** (2026-07-10) — schema unchanged from v0.57.0
> Hermes: tool-search (progressive tool disclosure) active in default profile

## 1. Hermes Tool-Search Redesign (highest impact — do first)

> **DONE 2026-08-10 (v0.6.0):** tool surface converted to 12 tools + 1 skill.
> See commit(s) after ece4a30. Remaining: schema description audit (§ below),
> live bridge verification (requires session restart).

Hermes now employs a **search-and-execute tool pattern** (`tools/tool_search.py`):
when any plugin/MCP tool exists, all non-core tools are hidden behind three
bridge tools — `tool_search`, `tool_describe`, `tool_call` — and their full
schemas only load on demand. In this profile it's already active
(`tools.tool_search: enabled: auto, threshold_pct: 10`), so the plugin's
tools are already deferred: the model sees the bridge plus a name+description
catalog listing (~1 line per tool; 53 tools render in `full` form at ~2.7K
chars, well under the 4K-token budget).

**Design principle for this pass (agreed with user):** no complete-parity
goal — only the operations an agent-operator actually performs. Expose
high-level affordances, not the raw API. Bake mechanics into handlers,
carry decisions in schema descriptions, keep one recipe skill.

**Terminology (agreed with user):** Caido's fuzzing domain is **automate** —
the tool names and all docs must say `automate`, not `fuzz`. The only
place "fuzz" survives is the literal `FUZZ` placeholder, which mimics
ffuf workflow for ease of use. Sweep all "fuzz"/"fuzzing" references in
README, skills, schemas, AGENTS.md after the rename.

### Target surface: 12 tools

**Keep (7):** *(implemented)*
- [x] `caido_onboard` — orient: project, scopes, intercept, recent traffic, findings count, hosted files, scope suggestion
- [x] `caido_health` — connectivity check (cheap troubleshooting probe)
- [x] `caido_search` — HTTPQL search of proxy history
- [x] `caido_recent` — recent requests
- [x] `caido_get` — full request/response by ID
- [x] `caido_findings` — list findings
- [x] `caido_create_finding` — record a finding

**Add (5):** *(implemented)*
- [x] `caido_replay` — send a request as-is or with optional edits (method/path/body/headers). Combines `replay` + `replay_with_edit`; edit is an optional modifier, one domain, one discoverable tool. Handler owns raw-request assembly.
- [x] `caido_automate` — one-call automate orchestration: source (request_id) + target value + payload list + strategy → create session, find FUZZ-slot byte offset, build full settings dict, start task, return `{session_id, task_id}`. Hides base64/byte-offset/settings-dict mechanics. Named `automate` per Caido's domain term.
- [x] `caido_automate_status` — poll automate task state/progress, return result counts. Full result bodies = Phase 4.
- [x] `caido_export_curl` — request ID → curl command (handoff to ffuf/bash).
- [x] `caido_auth_setup` — re-register preserved `handle_setup`: device-flow auth via subprocess isolation.

**Modify (1): `caido_get` becomes dual-namespace** *(implemented)* — the UI request-ID mismatch (see Known Issues) means a number quoted from the Caido UI is `metadata.id`, not `Request.id`. `caido_get(request_id)` now: (1) tries `request(id:)`, accepts only if the result's `metadata.id == requested`; (2) else scans `requestsByOffset` pages for `metadata.id == requested`, returns all matches (usually 1–2). Schema description updated: "Accepts both the GraphQL request id and the number shown in the Caido UI history table." Verified live: 3618→5218 (blog.inlanefreight.local), 2595→3511/3512 (corporate.wolt.com).

### Skills: 3 → 1 *(implemented)*

- [x] **Delete `caido:replay` skill** — content folds into `caido_replay` tool schema + short recipe lines.
- [x] **Delete `caido:utils` skill** — content folds into `caido_onboard` / `caido_auth_setup` / `caido_export_curl` tools. Auth error guidance stays in tool schemas/handlers.
- [x] **Rewrite `caido:automate` as a ~100-line automate cookbook** (not an API reference): strategy × payloads decision table (ALL/SEQUENTIAL/MATRIX/PARALLEL), URL-encoding + `${IFS}` pitfalls, IDOR/param/auth-bypass patterns, mapping of `caido_automate` / `caido_automate_status` to the workflow, auth.setup fallback note. Keep the name `automate` (Caido's domain term) — avoids a multi-file rename cascade (plugin.yaml, __init__, schemas, README, AGENTS.md, frontmatter).

### Deliberately NOT exposing as tools (library stays callable via execute_code)

- Findings update/delete, scope/filter/env/project mutations, replay collections/drafts, hosted-file upload, automate raw session CRUD, automate result bodies.
- Rationale: config or niche; agent asks the user or uses execute_code. Promote to tools only when a real use case appears. Do NOT build action-selector CRUD tools (`caido_manage` with `action:` param) — coupled-flag footgun, rare-use value.

### Schema description guidance (tool-search era)

- [ ] Re-audit all `schemas.py` descriptions against the hermes-plugin-development bar (function + params, no flag trivia, no worked examples) — descriptions drive `tool_search` BM25 and the catalog listing's first sentence.
- [ ] Ensure every schema has a proper `required` array — `validate_deferred_call_args` returns the schema when required args are missing, so the model self-repairs in one round-trip.
- [ ] Verification: after conversion, test live bridge discovery — `tool_search("replay request")`, `tool_search("automate parameter")`, `tool_search("create finding")` must hit the right tools.

## 2. Caido v0.57.x — Feature Gaps (deferred, not critical)

Schema in repo is **v0.57.0** (verified: `ReplayEntryWs`, `AutomateExtractor`,
`AutomateExtractorRegex`, `testExtractor` all present). v0.57.1 (2026-07-10)
is replay-page bugfixes only — no API changes, no schema regen needed.
v0.57.0 shipped features the plugin doesn't use yet; none are operator-critical:

- [ ] **WebSocket replay** (v0.57.0) — `ReplayEntryWs` types in schema; no WS-session functions in `lib/graphql/replay.py`. Add only if an agent-operator use case appears (low priority).
- [ ] **Automate custom extractors** (v0.57.0) — `AutomateExtractorRegex` + `testExtractor` in schema; no builder in `lib/payloads.py`. Relevant when Phase 4 result retrieval lands.
- [ ] **StreamQL** (v0.57.0) — WS-history filtering; defer with WS replay.
- [ ] **Global filters** — already handled (`create_filter` sends `global: False`). No action.
- [ ] Confirm AGENTS.md schema note reads "v0.57.x".

## 3. SDK Migration — Re-evaluate (blocked, low priority)

`../sdk-py` (community Python SDK) is now **caido-sdk-client 0.3.0** with
`caido-schema-proxy 0.57.1` (schema side caught up). Two blockers remain:

- [ ] **Python version gate** — SDK requires `>=3.12`; Hermes venv is **3.11.15**. Full adoption requires a Hermes venv Python bump (not in plugin's control) or an SDK version supporting 3.11 (doesn't exist yet).
- [ ] **Automate still missing** — generated schema has **zero** `AutomateSession` references. SDK covers replay (incl. WS), findings, scopes, filters, envs, projects, hosted files, requests, tasks list/cancel/finished — but NOT automate session CRUD, placeholders, payloads, start/pause/resume.
- [ ] **Decision:** do NOT migrate yet. Keep raw aiohttp GraphQL. Re-check when (a) SDK supports Python 3.11 or Hermes bumps its venv, AND (b) SDK gains `AutomateSession`. Update the stale "SDK is on 0.56.0" claim in `AGENTS.md`.
- [ ] If partial migration is ever wanted, the seam is: SDK for replay/findings/scopes, keep `lib/graphql/automate.py` raw. The tool/skill interface is the stable contract either way.

## 4. Packaging & Dependencies

- [x] **Add `pyproject.toml`** with `aiohttp` as a declared dependency (2026-08-10)
- [x] ~~Replace hardcoded venv path in `auth_helper.py`~~ — now uses `sys.executable`
- [ ] Install plugin into Hermes venv via `pip install -e .` (editable) — deferred: directory-plugin + symlink install works; packaging is for distribution
- [ ] Skills import via `import automate` — no `sys.path.insert` needed
  - **Reconsider after tool-search redesign:** with only one recipe skill left, the `sys.path.insert` import pattern shrinks to that one skill — still worth packaging, lower priority

## 5. Automate — Remaining Phases

**Agreed direction (2026-08-10, A+C):** implement Phase 4 result retrieval so
`caido_automate_status` returns what the fuzzer found (status codes, lengths,
bodies) — the tool must tell the truth about outcomes, not just "started".
Framing C is baked into guidance: the skill and tool descriptions steer heavy
enumeration to `caido_export_curl` + ffuf, and Caido Automate is positioned as
the *visible* (shared-workspace) fuzzer, not the best fuzzer.

- [x] **Phase 4: Result retrieval** — `get_entry_requests()` implemented (async + sync wrapper); `caido_automate_status` now returns count, status-code distribution, error counts, highlights, and full results (`brief: false`). Accepts `session_id` (stable), `entry_id` (durable), or `task_id` (in-progress). Verified live: 5-payload run → all results with payload→status mapping. (2026-08-10)
- [ ] Phase 5: Automate patterns (IDOR, parameter automate, auth bypass, rate limiting) — keep in the `caido:automate` cookbook; session/task control is handled by `caido_automate` / `caido_automate_status` tools
- [ ] Extractor builder + `testExtractor` (see §2) — natural companion to Phase 4 (extract results as columns)
- [x] **`caido_automate` URL-encoding default** — `url_encode: true` (default) percent-encodes payloads with the UI charset `:/?#[]{}@$&+ ,;=%<>`; set false for body/JSON/header fuzzing. Verified live: `test value with spaces` → `test%20value%20with%20spaces` → 200 (was 400). Decision: **Option A** — payloads written to need no processing; prefix/suffix/custom workflows deliberately not exposed (generate transformed payload lists instead). Skill + AGENTS.md updated. (2026-08-10)
- [x] **Shared-workspace guidance** — `caido_onboard` returns a `workspace.note`; `caido_replay`/`caido_automate` descriptions carry the "use Caido when the user should see it, curl/ffuf for private probing" rule; skill has a Caido-vs-terminal decision table; README/AGENTS.md document the principle. (2026-08-10)

## Known Issues

- [x] ~~Hardcoded paths break under Hermes profiles~~ — fixed via `CAIDO_PLUGIN_DIR`, `HERMES_HOME`, `sys.executable`
- [x] ~~`search()` / `recent()` no scope filtering~~ — fixed via active scope state set by `caido_onboard`
- [x] ~~`findings { id }` in onboard query~~ — fixed to `findings { count { value } }`
- [ ] Event loop conflicts in `caido_onboard` / `caido_health` — auth helper subprocess workaround works, but health/graphql calls still run inside agent's event loop
- [x] ~~**Automate settings dict must be complete**~~ — **FIXED 2026-08-10:** `AutomateSettingsInput` requires all fields (closeConnection, concurrency, extractors, payloads, placeholders, redirect, retryOnFailure, strategy, updateContentLength). `update_session` now fills safe defaults via `_complete_settings()`. Found during live handler test.
- [ ] **Automate session delete fails while a task exists** — a session with a running/completed task returns "Failed to delete automate session / User error". Cancel the task first (`cancel_task`), then delete. Worth a note in the skill + possibly auto-cancel in `delete_session`.
- [ ] **No `delete_finding` library wrapper** — schema has `deleteFindings` but `lib/graphql/findings.py` only has list/get/create/update. Add a sync + async wrapper if an agent-operator use case appears (finding lifecycle is mostly create/list).
- [x] ~~**`caido_create_finding` ignored the UI-number namespace**~~ — **FIXED 2026-08-10 (test drive):** the handler passed `request_id` straight to the `createFinding` mutation, which keys on Request.id. A UI number like 3618 attached the finding to the wrong request (daas instead of blog). Handler now resolves via `resolve_request_id` first. Verified live: finding attaches to Request.id 5218 / blog.inlanefreight.local.
- [x] ~~**Automate/replay traffic has no captured response in history**~~ — **RESOLVED by Phase 4 (2026-08-10):** the fuzzer's results were never in proxy history (`statusCode 0`) — they live in the automate entry. `caido_automate_status` now retrieves them via `get_entry_requests()`, so an agent judges outcomes from the status tool, not from history. The `status 0` in caido_search/caido_get for automate-generated traffic remains a Caido behavior, now documented in the skill.
- [ ] **Replay and automate session IDs share a small numeric space** — `caido_replay` returned `sessionId: 4, taskId: 3` while an automate session also had id 4 / task 3 (separate counters per domain). An agent holding a replay session id and passing it to automate (or vice versa) hits "not found" or the wrong object. The tools return ids without a domain qualifier — consider prefixing output (`replay:4` / `automate:4`) or documenting the namespace split in schema descriptions.
- [ ] **CONFIRMED (2026-08-10): UI request IDs ≠ GraphQL Request IDs — metadata.id namespace.** Verified live against 127.0.0.1:8080 (wolt project):
  - The Caido UI history table's ID column shows **`RequestMetadata.id`** (a group key), not **`Request.id`** (the per-request counter). They diverge — e.g. `Request.id=5218` (blog.inlanefreight.local) has `metadata.id=3618`; `Request.id=3511/3512` (corporate.wolt.com) have `metadata.id=2595`.
  - The plugin's `caido_get(request_id=...)` queries `request(id:)` = `Request.id`, so a number read from the UI (metadata.id) resolves to a **different request** or null. This is exactly the "request IDs in my UI did not match" report.
  - `requests` and `requestsByOffset` (the UI table query) return the **same** `Request.id` — so within one project the plugin's search/recent IDs are consistent with GraphQL; only the UI-visible column is metadata.id.
  - No `requestMetadata(id:)` query exists; HTTPQL cannot filter by metadata id (tested: `req.metadata.id.*` invalid) — so resolving a UI-quoted number requires a list scan, not a direct lookup.
  - **Fix direction:** make `caido_get` accept both namespaces — try `request(id:)` first, and on null/empty also scan `requests` (or `requestsByOffset`) for a node whose `metadata.id` matches, then fetch the first hit. Alternatively add a `metadata_id` param and document the distinction in the schema. Decide during the §1 tool redesign; the tool-search era makes this cheap to surface in descriptions.
  - **Workaround verified live (2026-08-10, screenshot-confirmed):** the resolution scan works. `requestsByOffset` pages in ID ASC order; matching `metadata.id` finds the right Request.id. Confirmed for 3618→5218 (blog.inlanefreight.local), 3619→5219 (content-autofill), 2595→3511/3512 (corporate.wolt.com). Fast path check matters: `request(id:)` returns a *different* request whose metadata.id doesn't match (e.g. request(3618) → daas, metadata 2661), so acceptance requires `direct.metadata.id == requested`, not just non-null.
  - **Recommended fix shape:** `caido_get(request_id)` becomes dual-namespace — (1) try `request(id:)`, accept only if result's `metadata.id == requested`; (2) else scan `requestsByOffset` pages for `metadata.id == requested`, return all matches (usually 1–2; e.g. 3511+3512 share 2595). Schema description tells the agent: "A number from the Caido UI is the request's metadata id; caido_get accepts both." This makes the user and the agent speak the same language with zero extra steps.
- [x] ~~**Guest mode broken against this instance**~~ — **FIXED 2026-08-10:** guest mode removed entirely. `_is_local_url()` deleted from `lib/graphql/client.py`; `_resolve_pat()` always raises on missing PAT; `_ensure_auth()` always authenticates (cached token → refresh → device flow), for local and remote alike. Docs updated: AGENTS.md, plugin.yaml, schemas.py, caido_tools.py guidance, skills/utils/SKILL.md. All instances require auth.
- [ ] **New:** verify `tool_search` discoverability after the §1 tool conversion — a deferred tool the model can't find via search is invisible; test with the real bridge
