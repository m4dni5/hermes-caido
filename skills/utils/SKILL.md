---
name: utils
description: Caido utility operations — auth setup, findings detail/update, export curl, scopes, filters, environments, projects via Python lib/
tags: [worker, offensive]
---

# Caido Utilities

## When to Use This Skill

Load this skill when you need to:
- Set up or troubleshoot Caido authentication (fresh install, token issues)
- Get finding details or update a finding
- Export requests as curl commands
- Get response-only view of a request
- Manage scopes, filters, environments, or projects

**For common operations, use the plugin tools directly** — `caido_search`, `caido_get`, `caido_findings`, `caido_create_finding`, `caido_health`, `caido_setup`.

## How to Use

Use `execute_code` (not `terminal`) to call these functions. The agent imports and calls them directly — no shell subprocess needed.

```python
# In an execute_code script:
import os, sys
sys.path.insert(0, os.path.join(os.environ["CAIDO_PLUGIN_DIR"], "lib"))
import http_requests
import findings
import management
import auth
```

## Authentication Setup

For fresh installs or token issues. The `caido_onboard` tool handles the happy path automatically.

```python
import auth

# Check auth status
status = auth.auth_status()
# Returns: {"token_cached": true, "token_expired": false, "connection_ok": true, ...}

# Test full connectivity
test = auth.test_connection()
# Returns: {"health": true, "auth": true, "query": true, ...}

# Configure credentials (runs auth flow in isolated subprocess)
result = auth.setup(pat="caido_...", url="https://caido.example.com")
# Returns: {"status": "success", "token_cached": true}

# Clear cached tokens
auth.clear_cache()
```

## Export Curl

```python
curl_data = http_requests.export_curl(request_id="12345")
print(curl_data["curl"])
# Output: curl -sS -H 'Cookie: ...' -d '{"key":"val"}' 'https://target/api'
```

## Get Response Only

```python
resp = http_requests.get_response(request_id="12345")
# Returns: {"id": "12345", "statusCode": 200, "responseRaw": "...", ...}
```

## Findings (detail/update only — list/create are plugin tools)

### Get finding details

```python
finding = findings.get_finding(finding_id="abc")
# Returns: {"id": "abc", "title": "IDOR", "description": "...", ...}
```

### Update finding

```python
result = findings.update_finding(
    finding_id="abc",
    title="Confirmed IDOR in user profile",
    description="Can access other users' data by changing user_id parameter",
    severity="high",
)
```

## Scope Management

```python
management.scopes()                              # List
management.get_scope(scope_id="1")               # Get details (name, allowlist, denylist)
management.create_scope(name="Target", allow=["*.target.com"])  # Create
management.rename_scope(scope_id="1", name="New Name")          # Rename only
management.update_scope(scope_id="1", name="New", allowlist=["*.new.com"], denylist=["*.old.com"])  # Full update (merges with current if partial)
management.delete_scope(scope_id="1")            # Delete
```

## Filter Preset Management

```python
management.filters()                             # List
management.create_filter(name="API Errors", httpql='req.path.cont:"/api/" AND resp.code.gte:400')
management.delete_filter(filter_id="1")          # Delete
```

## Environment Management

```python
management.environments()                        # List
management.create_environment(name="Staging", variables=[{"name": "URL", "value": "https://staging.target.com", "kind": "string"}])
management.delete_environment(env_id="1")        # Delete
```

## Project Management

```python
management.projects()                            # List
management.create_project(name="New Engagement") # Create
management.delete_project(project_id="1")        # Delete
```

## Task Management

```python
management.tasks()                               # List
management.cancel_task(task_id="1")              # Cancel
```

## Pitfalls

1. **All functions are synchronous** — just call them, no `asyncio.run()` needed
2. **Finding severity** — not a native Caido field, folded into description
3. **Filter alias** — must be URL-safe slug, auto-generated from name if not provided
4. **Environment variables** — `kind` field is required (use `"string"`)
