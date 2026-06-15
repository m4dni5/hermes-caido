# AGENTS.md — hermes-caido

A Hermes Agent plugin for the [Caido](https://caido.io) HTTP proxy. Enables AI agents to search proxy history, manage findings, replay requests, and run fuzzing campaigns against live targets.

## Architecture

```
hermes-caido/
├── __init__.py              # Plugin registration — tools + skills
├── plugin.yaml              # Plugin metadata (name, version, env vars)
├── schemas.py               # JSON Schema for registered tools
├── caido_tools.py           # Async tool handlers (called by Hermes)
├── auth_helper.py           # Standalone auth flow (subprocess isolation)
├── lib/
│   ├── sync.py              # sync_run() helper — asyncio.run() + close()
│   ├── http_requests.py     # Sync wrappers: search, recent, get, export_curl
│   ├── findings.py          # Sync wrappers: list, get, create, update
│   ├── replay.py            # Sync wrappers: sessions, entries, replay
│   ├── management.py        # Sync wrappers: scopes, filters, envs, projects
│   ├── automate.py          # Sync wrappers: sessions, tasks, update_session
│   ├── auth.py              # Sync wrappers: auth_status, setup, clear_cache
│   ├── placeholders.py      # Placeholder helpers: find_value, placeholder_for_param/header
│   ├── payloads.py          # Payload validation: strategy-aware, simpleList/number builders
│   └── graphql/
│       ├── client.py        # Core: aiohttp singleton, GraphQL transport, OAuth2 device flow
│       ├── http_requests.py # Async: search, recent, get, export_curl
│       ├── findings.py      # Async: findings CRUD
│       ├── replay.py        # Async: replay sessions/entries
│       ├── management.py    # Async: scopes, filters, envs, projects, hosted_files
│       ├── automate.py      # Async: automate sessions/tasks, update_session
│       └── auth.py          # Async: auth_status, setup, clear_cache, test_connection
└── skills/
    ├── replay/SKILL.md      # Session management, edit-and-replay, curl-through-proxy guidance
    ├── utils/SKILL.md       # Auth setup, findings CRUD, scopes, filters, envs, projects
    └── automate/SKILL.md    # FUZZ slot pattern, placeholders, payloads, task control
```

## Two-Layer Design

Every domain follows the same pattern:

1. **`lib/graphql/<domain>.py`** — async functions using raw GraphQL + aiohttp
2. **`lib/<domain>.py`** — sync wrappers via `sync_run()` for skill consumption

Skills call the sync wrappers in `execute_code` blocks. Tool handlers in `caido_tools.py` call the async functions directly.

## Key Design Decisions

### Skill-first for complex operations
Tools are for high-frequency, single-call operations (search, get, recent). Everything else lives in skills loaded on demand. This keeps the agent's context lean — the skill only loads when needed.

### Auth runs in a subprocess
The Hermes agent's async context interferes with aiohttp WebSocket connections (inherited SSL state, nested event loops). The auth flow runs in `auth_helper.py` as a fresh process. The `caido_onboard` tool handles the happy path; auth setup/troubleshooting lives in the `caido:utils` skill.

### No external SDK dependency (for now)
We use raw GraphQL strings against Caido's v0.57.0 schema. The official Python SDK (`caido-sdk-client`) is on 0.56.0 and lacks automate support. When the SDK catches up, we'll swap the GraphQL layer. The skill interface is the stable contract.

### FUZZ slot pattern for placeholders
Modify the raw request to embed `FUZZ` at the target location, then call `find_value(template, "FUZZ")` to get byte ranges. Payloads are bare data (`admin`, not `http://127.0.0.1/admin`). No preprocessors needed.

### Scope-aware workflow
Caido's GraphQL API has no concept of "the scope the history tab is filtering by" — the UI stores that client-side. The plugin bridges this gap:

1. **`caido_onboard` suggests a scope** — matches recent traffic hosts against scope allowlists via glob patterns. Returns `suggested_scope` with matched hosts and reasoning.
2. **Onboard sets the active scope** — stored in module-level state. All subsequent `search()` and `recent()` calls use it as the default filter.
3. **The agent should ask the user** if no scope is suggested (no recent traffic, or traffic doesn't match any scope) or if multiple scopes are plausible.
4. **Once a scope is chosen**, the agent relies on the active scope or passes `scope_id` explicitly.
5. **To override**, pass `scope_id=None` to search/recent to disable filtering (see full history).

This ensures the agent is always looking at the target, not background noise like `detectportal.firefox.com`.

## Working with the Codebase

### Adding a new GraphQL operation
1. Add the async function in `lib/graphql/<domain>.py`
2. Add the sync wrapper in `lib/<domain>.py` using `sync_run()`
3. If it's a tool handler, add it in `caido_tools.py` and register in `__init__.py`
4. If it's skill-only, document it in the relevant `skills/<name>/SKILL.md`

### Running code from skills
Skills use `execute_code` to call library functions:

```python
import os, sys
sys.path.insert(0, os.path.join(os.environ["CAIDO_PLUGIN_DIR"], "lib"))
import http_requests

results = http_requests.search(query='req.path.cont:"/api/"', limit=10)
```

### Checking syntax
```bash
python3 -m py_compile lib/graphql/client.py
python3 -m py_compile caido_tools.py
```

## Important Pitfalls

1. **`sync_run()` closes the session after each call** — `asyncio.run()` creates a fresh event loop, so the singleton session is always stale. Closing after each call is correct, not wasteful.

2. **`caido_onboard` must run in a subprocess for auth** — the Hermes agent's event loop breaks aiohttp WS handshakes. Use `auth_helper.py` for auth flows.

3. **Placeholder byte offsets are UTF-8 bytes, not characters** — multi-byte content produces different offsets.

4. **Automate `update_session` requires `connection` dict** — even when only changing settings, you must pass the connection info. Always fetch the session first.

5. **`interceptOptions.scope.scopeId` is intercept-only** — Caido doesn't expose "active scope for proxy history" via GraphQL. Scopes are per-mode in the UI (intercept/filter/history).

6. **URL-encode payload values when fuzzing inside URLs** — Caido's hosted file payloads don't auto-encode. Use the `urlEncode` preprocessor or pre-encode your wordlist. `${IFS}` bypasses space restrictions in shell commands passed through SSRF.

7. **Gopher/file/dict protocols disabled on many targets** — SSRF exploitation often requires HTTP-only approaches. Check what the server's libcurl supports.

## Environment

- **Plugin path:** `CAIDO_PLUGIN_DIR` env var (set automatically during registration, works under any profile)
- **Hermes home:** `HERMES_HOME` env var if set (profile-aware), otherwise `~/.hermes/`
- **Token cache:** `<hermes_home>/cache/caido-token.json`
- **Caido URL/PAT:** `<hermes_home>/.env` or env vars `CAIDO_URL` / `CAIDO_PAT`
- **Python executable:** `sys.executable` (same Python running the plugin)
- **Caido schema version:** 0.57.0

Skills import the library via:
```python
import os, sys
sys.path.insert(0, os.path.join(os.environ["CAIDO_PLUGIN_DIR"], "lib"))
```

## Future Work

See `TODO.md` for:
- Packaging with `pyproject.toml` + `pip install -e .`
- SDK migration when `caido-sdk-client` >= 0.57.0 + automate
- Automate phases 4–5 (result retrieval, fuzzing patterns)
- `caido:intercept` skill
