---
name: utils
description: Caido utility operations — findings, export curl, scopes, filters, environments, projects via Python lib/
tags: [worker, offensive]
---

# Caido Utilities

## When to Use This Skill

Load this skill when you need to:
- Manage findings (get details, update)
- Export requests as curl commands
- Manage scopes (list, create, delete)
- Manage filter presets (list, create, delete)
- Manage environments (list, create, delete)
- Manage projects (list, create, delete)

**For simple operations, use the plugin tools directly** — `caido_search`, `caido_get`, `caido_findings`, `caido_create_finding`, `caido_health`. No `execute_code` needed.

## Import Pattern

```python
import asyncio, sys
sys.path.insert(0, "/home/matt/src/hermes-caido/lib")

from http_requests import get, get_response, export_curl
from findings import list_findings, get_finding, create_finding, update_finding
from management import (
    scopes, get_scope, create_scope, delete_scope,
    filters, create_filter, delete_filter,
    environments, create_environment, delete_environment,
    projects, create_project, delete_project,
    hosted_files, tasks, cancel_task,
)
```

All functions are `async`. Wrap in `asyncio.run()`:

```python
result = asyncio.run(list_findings(limit=50))
```

## Export Curl

```python
curl_data = asyncio.run(export_curl(request_id="12345"))
print(curl_data["curl"])
# Output: curl -sS -X POST -H 'Cookie: ...' -d '{"key":"val"}' 'https://target/api'
```

## Get Response Only

```python
resp = asyncio.run(get_response(request_id="12345"))
# Returns: {"id": "12345", "statusCode": 200, "responseRaw": "...", ...}
```

## Finding Management

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

### List scopes

```python
all_scopes = asyncio.run(scopes())
# Returns: [{"id": "1", "name": "Target Corp"}, ...]
```

### Get scope details

```python
scope = asyncio.run(get_scope(scope_id="1"))
# Returns: {"id": "1", "name": "Target Corp", "allow": [...], "deny": [...]}
```

### Create scope

```python
scope = asyncio.run(create_scope(
    name="Target Corp",
    allow=["*.target.com", "*.target.io"],
    deny=["*.cdn.target.com"],
))
```

### Delete scope

```python
result = asyncio.run(delete_scope(scope_id="1"))
```

## Filter Preset Management

### List filters

```python
all_filters = asyncio.run(filters())
# Returns: [{"id": "1", "name": "API Errors", "alias": "api-errors", ...}]
```

### Create filter

```python
filt = asyncio.run(create_filter(
    name="API Errors",
    httpql='req.path.cont:"/api/" AND resp.code.gte:400',
))
```

### Delete filter

```python
result = asyncio.run(delete_filter(filter_id="1"))
```

## Environment Management

### List environments

```python
envs = asyncio.run(environments())
# Returns: [{"id": "1", "name": "Production", "variables": [...]}]
```

### Create environment

```python
env = asyncio.run(create_environment(
    name="Staging",
    variables=[
        {"name": "BASE_URL", "value": "https://staging.target.com", "kind": "string"},
    ],
))
```

### Delete environment

```python
result = asyncio.run(delete_environment(env_id="1"))
```

## Project Management

### List projects

```python
projs = asyncio.run(projects())
# Returns: [{"id": "1", "name": "Engagement 2024", "status": "active", ...}]
```

### Create project

```python
proj = asyncio.run(create_project(name="New Engagement", temporary=False))
```

### Delete project

```python
result = asyncio.run(delete_project(project_id="1"))
```

## Task Management

### List tasks

```python
all_tasks = asyncio.run(tasks())
# Returns: [{"id": "1", "type": "ReplayTask", "createdAt": "..."}]
```

### Cancel task

```python
result = asyncio.run(cancel_task(task_id="1"))
```

## Pitfalls

1. **All lib/ functions are async** — always wrap in `asyncio.run()`
2. **Finding severity** — not a native Caido field, folded into description
3. **Filter alias** — must be URL-safe slug, auto-generated from name if not provided
4. **Environment variables** — `kind` field is required (use `"string"`)
