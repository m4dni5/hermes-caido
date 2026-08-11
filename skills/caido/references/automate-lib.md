# Automate via lib/ — multi-placeholder & advanced campaigns

`caido_automate` (the tool) handles the single-slot case — one placeholder,
one payload list. Go to `lib/` when you need more control: MATRIX/PARALLEL
strategies (one payload set per placeholder), custom placeholder offsets,
or raw session editing. All operations below verified live against a Caido
0.57.x instance (2026-08).

## Setup

```python
import os, sys, base64
sys.path.insert(0, os.path.join(os.environ["CAIDO_PLUGIN_DIR"], "lib"))
import automate, placeholders, payloads
```

## FUZZ slot pattern (recommended)

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

## Parameter-aware placeholders (no FUZZ token)

When you'd rather target a parameter than a raw byte range:

```python
raw = base64.b64decode(full["raw"]).decode("utf-8")
ph = placeholders.placeholder_for_param(raw, "api")     # find the param's value bytes
payload_input = payloads.build_payload_input([["val1", "val2"]])
# then update_session(..., settings={"placeholders": ph, "payloads": payload_input, ...})
```

`placeholder_for_header(raw, "X-Forwarded-For")` works the same way for
header values.

## Strategy × payload sets

| Strategy | Sets needed | Constraint |
|---|---|---|
| `ALL` | 1 | Each value replaces ALL placeholders |
| `SEQUENTIAL` | 1 | Each value replaces placeholders one at a time |
| `MATRIX` | N (one per placeholder) | Cartesian product |
| `PARALLEL` | N (one per placeholder) | Sets must have equal length |

MATRIX/PARALLEL need one payload set *per placeholder* — pass a list of
lists to `build_payload_input`:

```python
payloads.build_payload_input([["a", "b"], ["1", "2"]])   # 2 placeholders, 2 sets
```

## Rules

1. `update_session` replaces the entire settings object — always fetch the
   session first, then pass `connection` through even if unchanged.
2. `settings` needs all fields the API requires; since v0.6.0 the library
   fills safe defaults (`_complete_settings()`) for what you omit
   (redirect, retryOnFailure, extractors, etc.).
3. URL-encoding: `build_payload_input(payload_sets, url_encode=True)`
   (default) attaches a urlEncode preprocessor with the UI charset —
   right for URL/path/query fuzzing. Pass `url_encode=False` for
   body/JSON/header fuzzing where literals matter.
4. Poll results with the **session id** (`caido_automate_status(session_id)`
   or `automate.get_entry_requests(entry_id)`) — tasks drop off the recent
   list after completion but sessions/entries persist.
