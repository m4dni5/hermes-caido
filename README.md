# hermes-caido

Hermes Agent plugin for the [Caido](https://caido.io) HTTP proxy. Search history, replay requests, run automate campaigns, manage findings — all from your AI agent.

## What It Does

**12 native tools** for the operations an agent-operator performs:

| Tool | Description |
|---|---|
| `caido_onboard` | Connect and gather full context — project, scopes, traffic, findings |
| `caido_health` | Check Caido connectivity |
| `caido_search` | Search proxy history with HTTPQL |
| `caido_recent` | Get recent intercepted requests |
| `caido_get` | Get request/response by ID — accepts Request.id **or** the UI history-table number |
| `caido_findings` | List security findings |
| `caido_create_finding` | Create a security finding |
| `caido_replay` | Replay a request, optionally edited (path/method/headers/body) |
| `caido_automate` | Run an automate campaign in one call (source + target + payloads + strategy) |
| `caido_automate_status` | Poll automate task status |
| `caido_export_curl` | Export a request as a curl command |
| `caido_auth_setup` | Run the device-code auth flow |

**One agent-operator cookbook skill** — the decision layer on top of the tools:

| Skill | Description |
|---|---|
| `caido:caido` | Shared-workspace guidance, tool map, replay & automate decisions, FUZZ slot pattern, patterns, pitfalls, HTTPQL reference |

## Caido vs the terminal — when to use this plugin

Most of what Caido does, an agent can do faster in the command line (curl,
ffuf). This plugin's value is that it creates a **shared workspace with the
user**: traffic you replay, automate runs, and findings you create appear in
the Caido UI the user is watching. Use Caido tools when the user should see or
build on the work. When you're exploring independently and the user doesn't
need to watch, use terminal tools instead — they're faster and don't clutter
the shared history.

- **Use Caido** for: replaying a request the user referenced, runs that should
  persist in proxy history, findings the user will review, anything the user
  should be able to click through and verify.
- **Use terminal** for: independent exploration, high-volume enumeration (export
  the request with `caido_export_curl` and run ffuf), quick one-off probes.

## Request IDs: what the UI shows vs what the tools return

The Caido UI history table shows the request's **metadata id**, which is a
different counter from the GraphQL `Request.id`. The plugin's `caido_get`,
`caido_replay`, `caido_automate`, and `caido_export_curl` accept **both** —
pass the number you see in the UI and it resolves automatically. When a number
is ambiguous (also a valid Request.id of a different request), the response
includes a `direct_match` note so you can disambiguate.

## Installation

```bash
git clone https://github.com/m4dni5/hermes-caido ~/.hermes/plugins/caido
```

All Caido instances require authentication — including local ones at
`127.0.0.1:8080`. Set `CAIDO_PAT` and `CAIDO_URL` in the Hermes `.env`, or use
`caido_auth_setup` to run the device-code flow.

## Usage

Start any Caido session with the onboard tool to get full context:

> "Onboard Caido"

Then use the tools naturally:

> "Search Caido for requests to /api"
> "Show me recent requests in Caido"
> "Get request 42 from Caido"  (42 = the number shown in the UI)
> "Create a finding for the IDOR I just found"
> "Replay request 42 with the path changed to /admin"
> "Export request 42 as curl"
> "Automate the id parameter with numbers 1-1000"

## Requirements

- [Hermes Agent](https://hermes-agent.nousresearch.com)
- Caido instance with API access
- Personal Access Token from Caido
