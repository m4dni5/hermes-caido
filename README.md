# hermes-caido

Hermes Agent plugin for the [Caido](https://caido.io) HTTP proxy. Lets your
agent search proxy history, replay and automate requests, manage findings, and
export requests as curl — all visible in the Caido UI you're watching.

## What It Does

**13 tools** for Caido operations:

| Tool | Description |
|---|---|
| `caido_onboard` | Connect and gather full context — project, scopes, traffic, findings |
| `caido_health` | Check Caido connectivity |
| `caido_search` | Search proxy history with HTTPQL |
| `caido_recent` | Get recent intercepted requests |
| `caido_get` | Get a request/response by ID
| `caido_findings` | List security findings |
| `caido_create_finding` | Create a security finding |
| `caido_delete_finding` | Delete a security finding |
| `caido_replay` | Replay a request, optionally edited, or iterate in one session |
| `caido_automate` | Run an automate campaign in one call |
| `caido_automate_status` | Poll a campaign and get its results |
| `caido_export_curl` | Export a request as a curl command |
| `caido_auth_setup` | Run the device-code auth flow |

The plugin also bundles a `caido:caido` skill — a cookbook the agent loads for
usage decisions (replay vs automate, payload encoding, common patterns,
pitfalls).

## Installation

```bash
hermes plugins install m4dni5/hermes-caido
```

For development, clone the repo and symlink it into your profile's plugins
directory (e.g. `~/.hermes/profiles/<profile>/plugins/caido`).

All Caido instances require authentication — including local ones. Set
`CAIDO_PAT` and `CAIDO_URL` in your Hermes `.env`, or run `caido_auth_setup`
to complete the device-code flow.

## Usage

Start with the onboard tool, then ask naturally:

> "Onboard Caido"
> "Search Caido for requests to /api"
> "Get request 42 from Caido"
> "Create a finding for the IDOR I just found"
> "Replay request 42 with the path changed to /admin"
> "Automate the id parameter with numbers 1-1000"

## Requirements

- [Hermes Agent](https://hermes-agent.nousresearch.com)
- Caido instance with API access
- Personal Access Token from Caido
