# Management via lib/ — scope/project/filter/env CRUD the tools don't expose

## When to use this

The tools only *read* management state: `caido_onboard` lists scopes,
`caido_search`/`caido_recent` filter by `scope_id`. There is **no tool** for
creating, renaming, updating, or deleting scopes, projects, filters,
environments, or hosted files. When the user asks for any of those — **do it
via this library, don't push them to the UI.** The user delegates because
they know the UI well; the library is the escape hatch.

## Setup

```python
import os, sys
sys.path.insert(0, os.path.join(os.environ["CAIDO_PLUGIN_DIR"], "lib"))
import management
```

The module exposes sync wrappers over `lib/graphql/management.py`. Every
function returns a plain dict/list.

## Operations

### Scopes

```python
management.scopes()                                            # list all
management.get_scope("1")                                      # one scope: {id, name, allowlist, denylist}
management.create_scope("new-target", allow=["*.example.com"]) # create; allow/deny optional
management.update_scope("1", allowlist=["*.example.com"], denylist=[])  # full update, merges partial
management.rename_scope("1", "renamed")                        # lightweight rename
management.delete_scope("1")
```

- `create_scope(name, allow=[...], deny=[...])` — `allow`/`deny` are the
  input names; `update_scope` uses `allowlist`/`denylist` (the returned
  shape).
- `update_scope` fetches the current scope first and merges partial
  updates — change just the name or just the allowlist without losing the
  other fields.
- After creating/editing a scope the user wants active, re-run
  `caido_onboard` (or call `set_active_scope` from `lib/http_requests.py`)
  so `caido_search`/`caido_recent` pick up the change.

### Projects

```python
management.projects()                              # list all
management.create_project("engagement-42")         # create (temporary=False default)
management.delete_project("project-id")
```

### Filters

```python
management.filters()                               # list all: {id, name, clause}
management.create_filter("no-images", 'req.path.ncont:"image"')   # name + HTTPQL
management.delete_filter("p:4")                    # note the "p:"-prefixed id
```

Filter ids are `p:`-prefixed (e.g. `p:4`) — use the id as returned, don't
assume a plain integer.

### Environments

```python
management.environments()                          # list all
management.create_environment("prod", variables=[{"name": "API_KEY", "value": "...", "kind": "SECRET"}])
management.delete_environment("env-id")
```

`create_environment` variable entries: `kind` is the enum
`EnvironmentVariableKind` — `PLAIN` or `SECRET` (uppercase only).

### Hosted files & automate tasks

```python
management.hosted_files()                          # list: {id, name, path, size, status}
management.tasks()                                 # list automate tasks
management.cancel_task("task-id")                  # cancel before deleting a session
```

`hosted_files()` returns `{id, name, path, size, status, createdAt,
updatedAt}` — the `id` is what you feed the `hostedFile` payload option for
wordlist fuzzing.

## Rules

1. **`deleteAutomateSession` fails while a task exists** — cancel the task
   first (`cancel_task`), then delete the session.
2. **Error unions expose `code`, not `message`** — a failed mutation
   returns the error's `code` field; the library surfaces it in the
   response dict.
3. **Request IDs are per-project** — scopes/filters/projects live inside
   the current project; switching projects changes what the list returns.

## Verified

All operations verified live against a Caido 0.57.x instance (2026-08):
reads for all six domains, plus a full scope create→get→update→rename→
delete cycle and filter create→delete.
