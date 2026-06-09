# hermes-caido

Hermes Agent plugin for the [Caido](https://caido.io) HTTP proxy. Search history, replay requests, manage findings — all from your AI agent.

## What It Does

**7 native tools** for the operations you use every engagement:

| Tool | Description |
|---|---|
| `caido_search` | Search proxy history with HTTPQL |
| `caido_recent` | Get recent intercepted requests |
| `caido_get` | Get request/response by ID |
| `caido_findings` | List security findings |
| `caido_create_finding` | Create a security finding |
| `caido_health` | Check Caido connectivity and auth |
| `caido_setup` | Diagnose auth issues, test connection |

**2 bundled skills** for everything else — loaded on demand, zero context cost until needed:

| Skill | Description |
|---|---|
| `caido:replay` | Session management, edit-and-replay, HTTPQL reference |
| `caido:utils` | Findings CRUD, export curl, scopes, filters, environments, projects |

## Installation

```bash
git clone https://github.com/m4dni5/hermes-caido ~/.hermes/plugins/caido
```

### Environment Variables

Add to `~/.hermes/.env`:

```
CAIDO_PAT=your_personal_access_token
CAIDO_URL=http://127.0.0.1:8081
```

The plugin will not load if either variable is missing.

### Authentication

Caido uses OAuth2 device code flow. On first use, the plugin will authenticate automatically using your PAT. Tokens are cached at `~/.config/caido-py/secrets.json`.

If you hit auth issues:

```
caido_setup(action="status")   # Check what's configured
caido_setup(action="test")     # Full connectivity test
caido_setup(action="clear")    # Clear token cache and re-auth
```

## Usage

The plugin tools are available immediately in any Hermes session. Just ask:

> "Search Caido for requests to /api"
> "Show me recent requests in Caido"
> "Get request 42 from Caido"
> "Create a finding for the IDOR I just found"

For complex operations, the agent loads the relevant skill automatically:

> "Replay request 42 through Caido"
> "Edit the path to /admin and replay it"
> "Export request 42 as curl"
> "List all scopes in Caido"

## Requirements

- [Hermes Agent](https://hermes-agent.nousresearch.com)
- Caido instance with API access
- Personal Access Token from Caido
