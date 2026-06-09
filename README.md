# hermes-caido

Hermes Agent plugin for the [Caido](https://caido.io) HTTP proxy. Search history, replay requests, manage findings — all from your AI agent.

## Architecture

```
hermes-caido/
├── plugin.yaml              # Manifest — tools, skills, env requirements
├── __init__.py              # register(ctx) — wires tools + skills
├── schemas.py               # Tool schemas (what the LLM sees)
├── caido_tools.py           # Async handlers (what runs when called)
├── skills/
│   ├── replay/
│   │   └── SKILL.md         # caido:replay — session management, edit-and-replay
│   └── utils/
│       └── SKILL.md         # caido:utils — findings, export curl, management
└── lib/                     # Core implementation (raw GraphQL via aiohttp)
    ├── client.py            # GraphQL client, OAuth2 auth, session management
    ├── auth.py              # Setup, auth status, cache management
    ├── http_requests.py     # search, recent, get, get_response, export_curl
    ├── replay.py            # replay, sessions, create_session, start_replay_task
    ├── findings.py          # list_findings, get_finding, create_finding, update_finding
    ├── management.py        # scopes, filters, envs, projects, tasks
    └── output.py            # Formatting helpers (compact, headers-only, truncation)
```

### Design Principles

**Plugin tools for the hot path, bundled skills for everything else.**

7 plugin tools handle the operations an agent calls on every engagement. Everything else — session management, edit-and-replay, findings CRUD, export curl, scopes/filters/envs/projects — is accessed via bundled skills that teach the agent to compose `lib/` functions through `execute_code`.

This keeps the tool count low (fewer context tokens consumed per turn) while preserving full API coverage.

**Raw GraphQL, no SDK dependency.**

The Caido Python SDK requires Python >=3.12. Hermes runs on 3.11. Rather than fighting version constraints, this plugin makes direct GraphQL calls via `aiohttp` (already in Hermes's venv). Zero external dependencies.

## Installation

```bash
# Clone to plugins directory
git clone https://github.com/m4dni5/hermes-caido ~/.hermes/plugins/caido

# Or symlink for development
ln -sf ~/src/hermes-caido ~/.hermes/plugins/caido
```

### Environment Variables

The plugin requires two environment variables:

| Variable | Description |
|---|---|
| `CAIDO_PAT` | Caido Personal Access Token (secret) |
| `CAIDO_URL` | Caido instance URL (e.g. `http://127.0.0.1:8081`) |

Set in `~/.hermes/.env` or as system environment variables. The plugin will not load if either is missing (`requires_env` gate).

### Authentication

Caido uses OAuth2 device code flow. The PAT is not used directly as a Bearer token — it approves the flow via caido.io, and the resulting access token is used for API calls.

Auth resolution order:
1. `CAIDO_PAT` / `CAIDO_URL` environment variables
2. `~/.hermes/.env` (dotenv fallback)
3. `~/.claude/config/secrets.json` under `caido` key

Token cache: `~/.config/caido-py/secrets.json`

## Plugin Tools

7 tools registered under the `caido` toolset:

| Tool | Description |
|---|---|
| `caido_search` | Search proxy history with HTTPQL |
| `caido_recent` | Get recent intercepted requests |
| `caido_get` | Get request/response by ID |
| `caido_findings` | List security findings |
| `caido_create_finding` | Create a security finding |
| `caido_health` | Check Caido health + GraphQL auth |
| `caido_setup` | Auth status, test connectivity, clear cache |

### Setup Tool Actions

```python
caido_setup(action="status")  # Check auth state, token info
caido_setup(action="test")    # Full connectivity test (health → auth → query)
caido_setup(action="clear")   # Clear token cache, force re-auth
caido_setup(action="setup")   # Configure credentials (pat, url)
```

## Bundled Skills

### caido:replay

Session management, edit-and-replay pattern, HTTPQL reference.

**Load:** `skill_view("caido:replay")`

**Covers:**
- Create replay sessions from existing requests (`requestSource.id`)
- Rename, delete, list sessions
- Create and list collections
- Edit request entries (base64 raw, connection info)
- Start replay tasks
- Full HTTPQL reference

**Key workflow (v0.57.0):**
```
createSession(request_id="123") → renameSession(id, "my-test") → startReplayTask(id)
```

**Edit-and-replay:**
```
getEntry(sessionId) → decode raw → modify → updateReplayEntryDraft(entryId, ...) → startReplayTask(sessionId)
```

### caido:utils

Findings CRUD, export curl, scopes, filters, environments, projects.

**Load:** `skill_view("caido:utils")`

**Covers:**
- Get/update findings
- Export requests as curl commands
- Scope management (list, create, delete)
- Filter preset management (list, create, delete)
- Environment management (list, create, delete)
- Project management (list, create, delete)
- Task management (list, cancel)

## Development

### Testing

```python
# Test auth
python3 -c "
import asyncio, sys
sys.path.insert(0, 'lib')
from auth import test_connection
print(asyncio.run(test_connection()))
"

# Test search
python3 -c "
import asyncio, sys
sys.path.insert(0, 'lib')
from http_requests import search
print(asyncio.run(search(query='req.path.ncont:\"/health\"', limit=3)))
"
```

### Pitfalls

1. **`is_async=True` required** — async handlers MUST pass `is_async=True` to `ctx.register_tool()`. Without it, the registry calls the handler synchronously, gets a coroutine object, and the tool silently fails.

2. **Never name a module after an installed package** — `lib/requests.py` collided with the `requests` package. Renamed to `http_requests.py`. Same risk with `json`, `os`, `sys`, `http`, `email`, `types`, `collections`.

3. **GraphQL Blob type is base64-encoded** — `raw` fields from Caido are base64-encoded. Decode before parsing as HTTP.

4. **v0.57.0 has no `StartReplayTaskInput`** — the `startReplayTask` mutation only accepts `sessionId`, not raw request content. Use `createSession` with `requestSource.id` to seed sessions.

5. **Session entries use relay connections** — `entries(first: 10) { edges { node { ... } } }`, not direct lists.

6. **`ReplayEntry` is an interface** — use `... on ReplayEntryHttp` inline fragments to access `raw`, `connection`, `draft` fields.

## Roadmap

### Done

- [x] Plugin tools (7): search, recent, get, findings, create_finding, health, setup
- [x] Bundled skill: caido:replay — session management, edit-and-replay
- [x] Bundled skill: caido:utils — findings CRUD, export curl, management
- [x] Raw GraphQL via aiohttp (no SDK dependency)
- [x] OAuth2 auth with token cache and refresh
- [x] Stale session recovery (event loop tracking + retry)
- [x] Base64-aware raw field handling

### Planned

- [ ] **caido:automate** — fuzzing pipeline (create/edit sessions, placeholders, payloads, start/stop tasks, results)
- [ ] **caido:intercept** — intercept control (enable/disable/status)
- [ ] **Streaming results** — subscribe to `createdAutomateEntryRequest` for live fuzz output
- [ ] **Hosted files** — wordlist management via Caido hosted files
- [ ] **WebSocket replay** — `ReplayEntryWs` support for WebSocket sessions
- [ ] **Workflow automation** — pre-built compositions (IDOR chain, auth bypass, fuzz-and-report)

### Schema Reference

Caido GraphQL schema is documented in the `caido-mode` skill references:
- `references/caido-graphql-schema.md` — full schema from Python SDK
- `references/caido-v057-schema-quirks.md` — v0.57.0 differences
- `references/caido-sdk-automate-schema.md` — automate/fuzz schema
- `references/caido-oauth2-auth-flow.md` — OAuth2 device code flow

## License

MIT
