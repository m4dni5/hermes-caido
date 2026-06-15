# hermes-caido

Hermes Agent plugin for the [Caido](https://caido.io) HTTP proxy. Search history, replay requests, manage findings, run fuzzing campaigns — all from your AI agent.

## What It Does

**7 native tools** for the operations you use every engagement:

| Tool | Description |
|---|---|
| `caido_onboard` | Connect and gather full context — project, scopes, traffic, findings |
| `caido_search` | Search proxy history with HTTPQL |
| `caido_recent` | Get recent intercepted requests |
| `caido_get` | Get request/response by ID |
| `caido_findings` | List security findings |
| `caido_create_finding` | Create a security finding |
| `caido_health` | Check Caido connectivity |

**Bundled skills** for everything else — loaded on demand, zero context cost until needed:

| Skill | Description |
|---|---|
| `caido:replay` | Session management, edit-and-replay, curl-through-proxy guidance |
| `caido:utils` | Auth setup, findings CRUD, export curl, scopes, filters, environments, projects |
| `caido:automate` | Automate (fuzzer) — session CRUD, FUZZ slot placeholders, payloads, task control |
| `caido:intercept` | Work in progress |

## Installation

```bash
git clone https://github.com/m4dni5/hermes-caido ~/.hermes/plugins/caido
```

## Usage

Start any Caido session with the onboard tool to get full context:

> "Onboard Caido"

Then use the tools naturally:

> "Search Caido for requests to /api"
> "Show me recent requests in Caido"
> "Get request 42 from Caido"
> "Create a finding for the IDOR I just found"

For complex operations, the agent loads the relevant skill automatically:

> "Replay request 42 through Caido"
> "Edit the path to /admin and replay it"
> "Export request 42 as curl"
> "Fuzz the id parameter with numbers 1-1000"

## Requirements

- [Hermes Agent](https://hermes-agent.nousresearch.com)
- Caido instance with API access
- Personal Access Token from Caido
