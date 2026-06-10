---
name: utils
description: Caido utility operations — findings detail/update, export curl, scopes, filters, environments, projects via Python lib/
tags: [worker, offensive]
---

# Caido Utilities

## When to Use This Skill

Load this skill when you need to:
- Get finding details or update a finding
- Export requests as curl commands
- Get response-only view of a request
- Manage scopes, filters, environments, or projects

**For common operations, use the plugin tools directly** — `caido_search`, `caido_get`, `caido_findings`, `caido_create_finding`, `caido_health`, `caido_setup`.

## Import Pattern

```python
import asyncio, sys
sys.path.insert(0, "/home/matt/src/hermes-caido/lib")

from http_requests import get_response, export_curl
from findings import get_finding, update_finding
from management import (
    scopes, get_scope, create_scope, delete_scope,
    filters, create_filter, delete_filter,
    environments, create_environment, delete_environment,
    projects, create_project, delete_project,
    hosted_files, tasks, cancel_task,
)
```

All functions are `async`. Wrap in `asyncio.run()`.

## Export Curl

```python
curl_data = asyncio.run(export_curl(request_id="12345"))
print(curl_data["curl"])
# Output: curl -sS -H 'Cookie: ...' -d '{"key":"val"}' 'https://target/api'
```

## Get Response Only

```python
resp = asyncio.run(get_response(request_id="12345"))
# Returns: {"id": "12345", "statusCode": 200, "responseRaw": "...", ...}
```

## Findings (detail/update only — list/create are plugin tools)

### Get finding details

```python
finding = asyncio.run(get_finding(finding_id="abc"))
# Returns: {"id": "abc", "title": "IDOR", "description": "...", ...}
```

### Update finding

```python
result = asyncio.run(update_finding(
    finding_id="abc",
    title="Confirmed IDOR in user profile",
    description="Can access other users' data by changing user_id parameter",
    severity="high",
))
```

## Scope Management

```python
asyncio.run(scopes())                              # List
asyncio.run(get_scope(scope_id="1"))               # Get details
asyncio.run(create_scope(name="Target", allow=["*.target.com"]))  # Create
asyncio.run(delete_scope(scope_id="1"))            # Delete
```

## Filter Preset Management

```python
asyncio.run(filters())                             # List
asyncio.run(create_filter(name="API Errors", httpql='req.path.cont:"/api/" AND resp.code.gte:400'))
asyncio.run(delete_filter(filter_id="1"))          # Delete
```

## Environment Management

```python
asyncio.run(environments())                        # List
asyncio.run(create_environment(name="Staging", variables=[{"name": "URL", "value": "https://staging.target.com", "kind": "string"}]))
asyncio.run(delete_environment(env_id="1"))        # Delete
```

## Project Management

```python
asyncio.run(projects())                            # List
asyncio.run(create_project(name="New Engagement")) # Create
asyncio.run(delete_project(project_id="1"))        # Delete
```

## Task Management

```python
asyncio.run(tasks())                               # List
asyncio.run(cancel_task(task_id="1"))              # Cancel
```

## Pitfalls

1. **All lib/ functions are async** — always wrap in `asyncio.run()`
2. **Finding severity** — not a native Caido field, folded into description
3. **Filter alias** — must be URL-safe slug, auto-generated from name if not provided
4. **Environment variables** — `kind` field is required (use `"string"`)
