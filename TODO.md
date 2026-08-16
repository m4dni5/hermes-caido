# TODO — hermes-caido

> Last reviewed: 2026-08-10
> Caido latest: **v0.57.1** (2026-07-10) — schema unchanged from v0.57.0
> Hermes: tool-search (progressive tool disclosure) active in default profile
> Current: 13 tools + `caido:caido` cookbook (v0.7.0)

## Open Work

### Near-term (high value)

- [ ] **Phase 5: Automate patterns** — IDOR, parameter automate, auth bypass, rate limiting. Keep in the `caido:caido` cookbook (patterns section exists, expand with worked examples if a real engagement needs them). Session/task control is already handled by the tools.
- [ ] **Extractor builder + `testExtractor`** (schema has `AutomateExtractorRegex` + `testExtractor`) — natural companion to Phase 4 result retrieval: extract result bodies as columns instead of raw payload→status pairs. Only when a campaign needs structured extraction.
- [ ] **Automate session delete fails while a task exists** — session with running/completed task returns "Failed to delete automate session / User error". Workaround documented in skill pitfall 9 (cancel first, then delete). Consider auto-cancel in `delete_session`.
- [ ] **Replay/automate session ID namespace ambiguity** — both domains return small numeric ids (`sessionId: 4` / `taskId: 3`) from separate counters. An agent holding a replay id and passing it to automate (or vice versa) hits not-found/wrong-object. Options: prefix tool output (`replay:4` / `automate:4`) or document the split in schema descriptions.
- [ ] **Packaging** — `pip install -e .` for distribution (pyproject.toml exists, v0.7.0). Deferred: directory-plugin + symlink install works; packaging is for other profiles/hosts.
- [x] **Skills import via `from lib import ...`** — the old pattern (`sys.path.insert(0, .../lib)` + `import automate`) mutated sys.path and pulled generic top-level names. Skills now insert the plugin root (`sys.path.insert(0, os.environ["CAIDO_PLUGIN_DIR"])`) and import the `lib` package (`from lib import automate, placeholders, payloads`). Done 2026-08-14; examples updated in AGENTS.md, `skills/caido/references/automate-lib.md`, and `management.md`.

### Re-evaluate when triggers appear

- [ ] **Scope/project lifecycle tools** — full CRUD works in `lib/management.py` (scopes: list/get/create/delete/rename/update; projects: list/create/delete; filters; environments), intentionally NOT tool surface. Skill's "Scope & project lifecycle (via lib/)" section tells agents to use it via execute_code. Add a compact tool only if a recurring mid-engagement pattern appears (e.g. "onboard new target + make scope + start testing" as one delegated instruction).
- [ ] **WebSocket replay** (v0.57.0) — `ReplayEntryWs` types in schema; no WS-session functions in `lib/graphql/replay.py`. Only if an agent-operator use case appears (low priority).
- [ ] **StreamQL** — WS-history filtering; defer with WS replay.
- [ ] **SDK migration** — blocked: SDK requires Python ≥3.12 (Hermes venv is 3.11.15) AND generated schema has zero `AutomateSession` references. Keep raw aiohttp GraphQL. Re-check when (a) Hermes bumps venv or SDK supports 3.11, AND (b) SDK gains AutomateSession. Partial-migration seam if ever wanted: SDK for replay/findings/scopes, keep `lib/graphql/automate.py` raw.
- [ ] **Event loop conflicts in onboard/health** — resolved-by-design: auth WebSocket runs subprocess-isolated (`_setup_via_subprocess`); regular GraphQL is loop-safe (`_current_loop` tracking + `_is_session_stale` close/recreate + one-shot retry; `sync_run` closes after each call; `close()` resets `_current_loop`). No connection issues observed since the auth rewrite. Only re-open if a session reports flaky first-call behavior.

## Recently Completed (don't redo)

- **13-tool surface + 1 skill (v0.7.0)** — tool-search redesign done: onboard/health/search/recent/get/findings/create_finding/delete_finding/replay/automate/automate_status/export_curl/auth_setup. Schema descriptions carry decisions; skill carries the cookbook.
- **Dual-namespace request IDs** — `caido_get`/`caido_replay`/`caido_automate`/`caido_export_curl`/`caido_create_finding` accept UI metadata.id AND Request.id (resolver: `resolve_request_id` in `lib/graphql/http_requests.py`). Verified live (3618→5218 etc).
- **Phase 4 result retrieval** — `caido_automate_status` returns status_codes/errors/highlights/results via `get_entry_requests()`. Poll with `session_id` (stable) / `entry_id` (durable) / `task_id` (in-progress).
- **Replay result + iteration mode** — `caido_replay` returns the response outcome; `session_id` mode edit-and-resends in one session (appends to history).
- **Automate url_encode default (Option A)** — payloads percent-encoded with UI charset by default; `url_encode: false` for body/JSON/header. Payloads written to need no processing; prefix/suffix/custom workflows deliberately not exposed.
- **Scope-aware search** — `caido_onboard` sets active scope, reports `active_scope`; `caido_search`/`caido_recent` take `scope_id` (omit = active, "" = full history). Sync wrappers default to `_UNSET` not None.
- **Proxy injection documented** — Caido proxy reachable at 127.0.0.1:8080; curl -x / -sk lands traffic in history (the "no proxy listener" finding from an earlier session was wrong — missing -k for Caido's MITM CA).
- **Management CRUD fixed + verified** — scope/project/filter/env CRUD in `lib/management.py` was broken against live schema (error unions read `message` instead of `code`; GET_SCOPE asked for allow/deny not allowlist/denylist). All fixed, live round-trips pass.
- **Skill rename to `caido:caido`** — general agent-operator cookbook, general-first ordering, all 13 tools named, frontmatter trigger self-contained.
- **Onboard `next_step` key** — `handle_onboard` returns a top-level imperative `next_step` telling the model to `skill_view("caido:caido")` before Caido work; the redundant sentence was removed from `workspace.note` so the instruction lives in one place. Done after auditing skill-vs-description split (most mechanics already baked in).
- **Skill-only guardrails baked into descriptions** — `caido_replay` now warns edits pass through verbatim (pre-encode `%20`/`%27`, unlike automate); `caido_search` notes an empty result usually means traffic is outside the active scope (retry `scope_id=""`). The two genuine error surfaces that were skill-only are now in always-read tool descriptions.
- **Schema sanitizer test harness fixed** — `_schemas()` never called `load_plugin()`, so the `hermes_plugins_test` namespace wasn't created and all 4 sanitizer tests failed on import (`ModuleNotFoundError`). One-line fix; 8/8 tests pass.

## Known Issues (still open, above)

- Automate session delete while task exists
- Replay/automate session ID namespace ambiguity
- SDK migration blockers (Python 3.12 + missing AutomateSession)

## Verified Fixed (don't re-open)

- Guest mode removed — all instances require auth (2026-08-10)
- `create_finding` UI-number resolution — handler resolves via `resolve_request_id` before mutation
- Automate settings dict completeness — `_complete_settings()` fills required fields
- Hardcoded paths under Hermes profiles — `CAIDO_PLUGIN_DIR` / `HERMES_HOME` / `sys.executable`
- Metadata.id namespace resolution — dual-namespace resolver (see Recently Completed)
- Tool-search discoverability — live bridge verified after restart
