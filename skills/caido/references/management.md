# Management Library Guide — scope/project/filter/env CRUD via lib/

Scope, project, filter, and environment mutations are **not tool surface** —
the tools only read them (onboard, `caido_search` scope_id). When the user
asks to create, rename, update, or delete one, **do it via this library —
don't push them to the UI.** All operations below verified live against a
Caido 0.57.x instance (2026-08).

## Setup

```python
import os, sys
sys.path.insert(0, os.path.join(os.environ["CAIDO_PLUGIN_DIR"], "lib"))
import management
```

The module exposes sync wrappers over `lib/graphql/management.py`. Every
function returns a plain dict/list.

## Scopes

```python
management.scopes()                                            # list all
management.get_scope("1")                                      # one scope: {id, name, allowlist, denylist}
management.create_scope("new-target", allow=["*.example.com"]) # create; allow/deny optional
management.update_scope("1", allowlist=["*.example.com"], denylist=[])  # full update, merges partial
management.rename_scope("1", "renamed")                        # lightweight rename
management.delete_scope("1")
```

Notes:
- `create_scope(name, allow=[...], deny=[...])` — `allow`/`deny` are the
  input names; `update_scope` uses `allowlist`/`denylist` (the returned
  shape).
- `update_scope` fetches the current scope first and merges partial
  updates — you can change just the name or just the allowlist without
  losing the other fields.
- After creating/editing a scope the user wants active, re-run
  `caido_onboard` (or call `set_active_scope` from `lib/http_requests.py`)
  so `caido_search`/`caido_recent` pick up the change.

## Projects

```python
management.projects()                              # list all
management.create_project("engagement-42")         # create (temporary=False default)
management.delete_project("project-id")
```

## Filters

```python
management.filters()                               # list all (id, name)
management.create_filter("no-images", 'req.path.ncont:"image"')   # name + HTTPQL
management.delete_filter("p:4")                    # note the "p:"-prefixed id
```

## Environments

```python
management.environments()                          # list all
management.create_environment("prod", variables=[{"name": "API_KEY", "value": "...", "kind": "SECRET"}])
management.delete_environment("env-id")
```

`create_environment` variable entries: `kind` is the enum
`EnvironmentVariableKind` — `PLAIN` or `SECRET` (uppercase only).

## Hosted files & automate tasks

```python
management.hosted_files()                          # list hosted files (wordlists etc.)
management.tasks()                                 # list automate tasks
management.cancel_task("task-id")                  # cancel before deleting a session
```

## Pitfalls

- **`deleteAutomateSession` fails while a task exists** — cancel the task
  first (`cancel_task`), then delete the session.
- **Error unions expose `code`, not `message`** — a failed mutation returns
  the error's `code` field; the library surfaces it in the response dict.
- **Request IDs are per-project** — scopes/filters/projects live inside the
  current project; switching projects changes what the list returns.
