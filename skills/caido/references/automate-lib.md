# Automate via lib/ — advanced campaigns the tool doesn't cover

## When to use this

`caido_automate` (the tool) covers the single-slot case: one placeholder,
one payload list, `ALL`/`SEQUENTIAL` strategies. Escape to `lib/` when you
need:

- **MATRIX / PARALLEL** strategies — one payload set *per placeholder*
- **Custom placeholder offsets** — a target that isn't a simple `FUZZ` swap
- **Parameter-aware placeholders** — target a named param or header directly
- **Session lifecycle** — rename, duplicate, delete, pause/resume tasks
- **Raw session editing** — full control over the raw request bytes

If the tool's single-slot case covers your need, use the tool — it's fewer
calls and validated.

## Setup

```python
import os, sys
sys.path.insert(0, os.environ["CAIDO_PLUGIN_DIR"])
from lib import automate, placeholders, payloads
```

## Operations

### Session lifecycle

```python
automate.sessions()                                    # list all sessions
session = automate.create_session(request_id="5218")   # seed from a proxy request
automate.rename_session(session_id, "new-name")
automate.duplicate_session(session_id)                 # copy a session
automate.delete_session(session_id)
```

`create_session()` without `request_id` makes an empty session — you'll
need `update_session` with raw + connection before it can run.

### FUZZ slot pattern (recommended)

Embed the literal token `FUZZ` at the exact target location in the raw
request, then use its byte range as the placeholder. Payloads become bare
data — URL structure stays baked into the template.

```python
session = automate.create_session(request_id="5218")
session_id = session["id"]
full = automate.get_session(session_id)
raw = base64.b64decode(full["raw"]).decode("utf-8")     # raw is a Blob — decode first

template = raw.replace("id=42", "id=FUZZ")
ranges = placeholders.find_value(template, "FUZZ")      # byte offsets (UTF-8 bytes, not chars)

automate.update_session(session_id,
    raw=template,
    connection={"host": full["connection"]["host"],
                "port": full["connection"]["port"],
                "isTLS": full["connection"]["isTLS"]},
    settings={
        "placeholders": ranges,
        "payloads": payloads.build_payload_input([["1", "2", "3", "admin"]]),
        "strategy": "ALL",
    })
result = automate.start_task(session_id)
```

### Parameter-aware placeholders (no FUZZ token)

Target a parameter by name instead of a raw byte range:

```python
raw = base64.b64decode(full["raw"]).decode("utf-8")
ph = placeholders.placeholder_for_param(raw, "api")     # find the param's value bytes
payload_input = payloads.build_payload_input([["val1", "val2"]])
# then update_session(..., settings={"placeholders": ph, "payloads": payload_input, ...})
```

`placeholder_for_header(raw, "X-Forwarded-For")` works the same way for
header values.

### Payload builders

```python
payloads.build_payload_input([["a", "b"], ["1", "2"]])   # 2 placeholders, 2 sets
payloads.build_number_payload(1, 100, increments=1, min_length=4)  # sequential numbers (IDOR)
payloads.add_prefix(payload_input, "http://127.0.0.1/")  # mutate a payload input
payloads.add_suffix(payload_input, "\"")
```

`build_number_payload` is the engine for sequential enumeration — the
skill's IDOR pattern. Zero-pad with `min_length`.

### Task control & results

```python
automate.list_tasks()                                   # list recent tasks
automate.cancel_task(task_id)                           # stop a run
automate.pause_task(task_id)
automate.resume_task(task_id)
automate.get_entry_requests(entry_id, limit=50, order=None, filter_code=None)
```

`get_entry_requests` is the lib-level result retrieval (the same engine
`caido_automate_status` uses):
- `order`: `{"by": "RESP_STATUS_CODE", "ordering": "DESC"}` — also
  `RESP_LENGTH`, `POSITION`
- `filter_code`: an HTTPQL string to filter the entry's requests
- Returns `{entry, count, results}` — each result has `sequence_id`,
  `payloads`, and the request/response pair

## Rules

1. **`update_session` replaces the entire settings object** — always fetch
   the session first, then pass `connection` through even if unchanged.
2. **Settings defaults are filled for you** — since v0.6.0 the library
   completes `redirect`, `retryOnFailure`, `extractors`, etc.
   (`_complete_settings()`) when you omit them.
3. **URL-encoding is on by default** — `build_payload_input(..., url_encode=True)`
   attaches a urlEncode preprocessor with the UI charset. Pass
   `url_encode=False` for body/JSON/header fuzzing where literals matter.
4. **Poll with the session id** — `caido_automate_status(session_id)` or
   `automate.get_entry_requests(entry_id)`. Tasks drop off the recent list
   after completion but sessions/entries persist.
5. **Deleting a session with a live task fails** — cancel the task first
   (`cancel_task`), then `delete_session`.

## Verified

All operations verified live against a Caido 0.57.x instance (2026-08);
payload builders checked against the library source.
