# hermes-caido — Design Notes

The project-specific rationale for the hermes-caido plugin. **This file records
*why*; it is not an instruction file.** Reusable Hermes-plugin and coding
guidance lives in `AGENTS.md`; the tool schemas are the documentation the model
reads at call time.

## What this is

A Hermes Agent plugin for the Caido HTTP proxy — search proxy history, manage
findings, replay requests, and run automate campaigns against live targets.
The plugin is a thin, opinionated wrapper over Caido's GraphQL API; it exists to
make the agent's Caido work *visible* in the UI the operator is watching, not to
be the best possible automate engine.

## Architecture

```
hermes-caido/
├── __init__.py              # Plugin registration — 13 tools + 1 skill
├── plugin.yaml              # Plugin metadata (name, version, env vars)
├── schemas.py               # JSON Schema for registered tools
├── caido_tools.py           # Async tool handlers (called by Hermes)
├── auth_helper.py           # Standalone auth flow (subprocess isolation)
├── lib/
│   ├── sync.py              # sync_run() helper — asyncio.run() + close()
│   ├── <domain>.py          # Sync wrappers for skill consumption
│   └── graphql/
│       ├── client.py        # Core: aiohttp singleton, GraphQL transport, OAuth2 device flow
│       └── <domain>.py      # Async functions using raw GraphQL + aiohttp
└── skills/
    └── caido/SKILL.md       # Agent-operator cookbook (judgment layer)
```

## Two-layer design (async core + sync wrappers)

Every domain follows the same pattern:

1. `lib/graphql/<domain>.py` — async functions using raw GraphQL + aiohttp
2. `lib/<domain>.py` — sync wrappers via `sync_run()` for skill consumption

Tool handlers in `caido_tools.py` call the async layer directly; skill
`execute_code` blocks call the sync wrappers. The sync wrapper **must `close()`
the session after each call** — `asyncio.run()` creates a fresh event loop, so a
singleton session is always stale. Closing after each call is correct, not
wasteful.

## Design decisions

**Tool-first (tool-search era).** Hermes uses progressive tool disclosure: all
non-core tools sit behind `tool_search`/`tool_describe`/`tool_call`, and schemas
load on demand. The old context-cost rationale for hiding operations in skills
is gone — every operation an agent-operator performs is a registered tool (13
total), and the descriptions carry the decisions. The one remaining skill
(`caido:caido`) is the agent-operator cookbook — shared-workspace guidance, tool
map, replay/automate decisions, pitfalls — the judgment layer that doesn't fit a
tool schema.

**Caido is the shared workspace.** The plugin's value is collaboration, not
capability: most of what Caido does an agent can do faster in the terminal.
Traffic replayed, automate runs, and findings created through the plugin appear
in the Caido UI the user is watching — that's the shared surface. Tool
descriptions and the skill carry the same guidance:
**use Caido when the user should see or build on the work; use curl/ffuf for
private exploration**. The plugin never claims to be the best automate engine —
it's the best *visible* one.

**Auth runs in a subprocess.** The Hermes agent's async context interferes with
aiohttp WebSocket connections (inherited SSL state, nested event loops). The
auth flow runs in `auth_helper.py` as a fresh process. `caido_auth_setup`
handles setup/troubleshooting as a tool; normal GraphQL paths self-heal via
the cached token.

**All instances require authentication.** Every Caido instance requires an
access token — including local ones at `127.0.0.1:8080`. The client tries, in
order: cached token → token refresh → full device code flow (PAT from
`CAIDO_PAT` env/`.env`). There is no guest mode; an unauthenticated `requests`
query returns `INVALID_TOKEN`. On auth failure the tool guidance directs the
agent to run `caido_auth_setup`.

**Auth error guidance.** All error paths in tool handlers and the client layer
include explicit guidance: **"Run caido_auth_setup"**. The agent follows it
whenever a Caido tool returns an auth-related error.

**No external SDK dependency (for now).** Raw GraphQL strings against Caido's
v0.57.x schema. The community SDK (`caido-sdk-client`) is on 0.3.0 / schema
proxy 0.57.1 but requires Python ≥ 3.12 (Hermes venv is 3.11) and lacks Automate
session support. When the SDK catches up, swap the GraphQL layer — the
tool/skill interface is the stable contract.

**ID namespace resolution (UI numbers).** The Caido UI history table shows
`metadata.id` (a group key), which differs from the GraphQL `Request.id`.
`lib/graphql/http_requests.py` has a resolver that tries `request(id:)` and
falls back to a `requestsByOffset` scan by `metadata.id`. `caido_get`,
`caido_replay`, `caido_automate`, and `caido_export_curl` accept both namespaces
automatically. Verified live: get(3618) → 5218, ambiguous matches surface all
candidates rather than guessing.

**FUZZ slot pattern for placeholders.** Modify the raw request to embed `FUZZ`
at the target location, then call `find_value(template, "FUZZ")` to get byte
ranges. Payloads are bare data (`admin`, not `http://127.0.0.1/admin`).
`caido_automate` URL-encodes payloads by default (UI charset); pass
`url_encode: false` for body/JSON/header fuzzing where literals matter. Write
payloads to need no processing (Option A): embed quoting/termination directly
rather than reaching for prefix/suffix preprocessors. `${IFS}` bypasses space
restrictions in shell commands passed through SSRF.

**Replay sessions: one-shot vs iteration.** `caido_replay(request_id=...)`
creates a new session per call — right for one-off replays.
`caido_replay(session_id=...)` edits the session's latest entry and resends,
appending to the same session's history (the UI's History drop-down + arrows).
Use iteration mode to group auth-bypass/parameter attempts in one session.
`replay_in_session()` in `lib/graphql/replay.py`; `_apply_mutations()` is shared
with `replay_with_edit()`.

**Scope-aware workflow.** Caido's GraphQL API has no concept of "the scope the
history tab is filtering by" — the UI stores that client-side. The plugin
bridges this gap (v0.7.1: no onboard tool — orientation is implicit):
1. **One-shot context envelope** (`lib/graphql/context.py`): the first
   successful read call (search/recent/get) runs a lightweight
   project+scopes query alongside the requested operation, matches recent
   traffic hosts against scope allowlists (glob patterns), and attaches a
   one-time `context` block to that response — project, scopes,
   `suggested_scope` with matched hosts, `active_scope` (the scope now set),
   recent hosts. Ambiguous matches (tie between scopes) select nothing.
2. The envelope sets module-level active scope state; all subsequent
   `search()`/`recent()` calls use it as the default filter. Subsequent
   calls skip the envelope entirely — zero added latency after the first.
3. When no scope is suggested (no recent traffic, or traffic doesn't match
   any allowlist), no scope is set — the context block says so, and the
   agent can pass `scope_id=""` (full history) or ask the user.
4. The envelope never raises: auth errors mark it done for the session
   (the operation's own error surfaces the auth problem); other errors
   retry up to three times.
5. Once a scope is chosen, the agent relies on the active scope or passes
   `scope_id` explicitly.
6. To override, the `scope_id` sentinel semantics matter: `_UNSET` (default) =
   active scope; explicit `None` or `""` = disable filtering (see full history);
   a scope id = filter by that scope.

This keeps the agent looking at the target, not background noise like
`detectportal.firefox.com`. When search comes back empty, check the active scope
before concluding the traffic doesn't exist.

**Proxy injection.** The Caido proxy listener is reachable from the shell
(commonly `127.0.0.1:8080`). `curl -x http://127.0.0.1:8080 <url>` sends traffic
through it; HTTPS requires `-k` because Caido MITMs with its own CA. Proxied
traffic lands in history, so automate/replay can source it.

## Gotchas (each with the *why*)

- **Import strategy — package-relative, never `sys.path` mutation in the
  framework path.** `caido_tools.py` and the `lib/*` sync wrappers use
  package-relative imports (`from .lib.graphql...`, `from .sync import`). Do NOT
  revert to `sys.path.insert(0, .../lib)` + bare `from graphql...` /
  `from output...`: it mutates the shared process's `sys.path` and pulls generic
  top-level names that can collide with stdlib/third-party modules. The
  framework loader imports the plugin as a namespaced package
  (`hermes_plugins.caido`) where relative imports resolve, so no path trickery
  is needed. Two special cases: `auth_helper.py` runs standalone
  (`python3 auth_helper.py`), so it inserts the plugin *root* on `sys.path` and
  imports `lib.graphql.client` (never the generic `graphql` name); the skill
  `execute_code` snippets insert `CAIDO_PLUGIN_DIR` and do `from lib import
  ...`. The root `__init__.py` has a try/except relative→absolute fallback
  because pytest imports it as a bare module (the dir name `hermes-caido` has a
  hyphen, invalid as a package name, so it can't be `tests`' parent).
- **`sync_run()` closes the session after each call** — `asyncio.run()` creates
  a fresh event loop, so the singleton session is always stale. Closing after
  each call is correct, not wasteful.
- **Auth must run in a subprocess** — the Hermes agent's
  event loop breaks aiohttp WS handshakes. Use `auth_helper.py` for auth flows.
- **Placeholder byte offsets are UTF-8 bytes, not characters** — multi-byte
  content produces different offsets.
- **Automate `update_session` requires `connection` dict** — even when only
  changing settings, you must pass the connection info. Always fetch the session
  first.
- **`interceptOptions.scope.scopeId` is intercept-only** — Caido doesn't expose
  "active scope for proxy history" via GraphQL. Scopes are per-mode in the UI
  (intercept/filter/history).
- **URL-encoding is on by default** — `caido_automate` percent-encodes payloads
  with the UI charset (spaces/reserved chars → `%XX`). Set `url_encode: false`
  when fuzzing bodies/JSON/headers where literal values matter.
- **Gopher/file/dict protocols disabled on many targets** — SSRF exploitation
  often requires HTTP-only approaches. Check what the server's libcurl supports.

## Test plan

The regression suite covers the two failure classes that have bitten these
plugins: the framework-loader import behavior and schema sanitization. It needs
the Hermes framework on `PYTHONPATH` for the sanitizer import.

```bash
PYTHONPATH=/path/to/hermes-agent \
  /path/to/hermes/venv/bin/python -m pytest tests/ -q
```

Layout:
- `tests/test_plugin_load.py` — loader semantics, 13-tool registration,
  no-sys.path-mutation guard, sync-wrapper imports.
- `tests/test_schema_sanitizer.py` — schemas survive `sanitize_tool_schemas`
  with `properties`/`required` intact, no top-level combinators.

## Environment

- **Plugin path:** `CAIDO_PLUGIN_DIR` env var (set automatically during
  registration, works under any profile)
- **Hermes home:** `HERMES_HOME` env var if set (profile-aware), otherwise
  `~/.hermes/`
- **Token cache:** `<hermes_home>/cache/caido-token.json`
- **Caido URL/PAT:** `<hermes_home>/.env` or env vars `CAIDO_URL` / `CAIDO_PAT`
  (required — all instances, including local, require auth)
- **Python executable:** `sys.executable` (same Python running the plugin)
- **Caido schema version:** 0.57.x

Skills import the library via:
```python
import os, sys
sys.path.insert(0, os.environ["CAIDO_PLUGIN_DIR"])
from lib import http_requests, management, automate, replay, findings
```

## Working with the codebase

### Adding a new GraphQL operation
1. Add the async function in `lib/graphql/<domain>.py`
2. Add the sync wrapper in `lib/<domain>.py` using `sync_run()`
3. If it's a tool handler, add it in `caido_tools.py` and register in `__init__.py`
4. If it's skill-only, document it in the relevant `skills/<name>/SKILL.md`

### Running code from skills
Skills use `execute_code` to call library functions:

```python
import os, sys
sys.path.insert(0, os.environ["CAIDO_PLUGIN_DIR"])
from lib import http_requests

results = http_requests.search(query='req.path.cont:"/api/"', limit=10)
```

### Checking syntax
```bash
python3 -m py_compile lib/graphql/client.py
python3 -m py_compile caido_tools.py
```

## Future work

See `TODO.md` for the open items:
- Automate patterns (Phase 5), extractor builder
- SDK migration when `caido-sdk-client` >= 3.12-compatible + automate support
- Packaging via `pip install -e .` (pyproject.toml exists)
- Known issues: session-delete-with-task, replay/automate ID namespace split,
  event-loop conflicts
