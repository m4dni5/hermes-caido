# HTTPQL — the caido_search query language

## When to use this

HTTPQL is the filter language for proxy traffic. The quick facts in
SKILL.md cover the common cases; load this reference when you need the
full field/operator surface — or when you're passing HTTPQL into a
library function (`create_filter`, `get_entry_requests(filter_code=...)`)
and need exact syntax.

Authoritative source: https://docs.caido.io/app/reference/httpql

## Syntax

```
namespace.field.operator:value
```

- String values are **quoted**: `req.path.cont:"/admin"`
- Integers and booleans are **unquoted**: `resp.code.gte:400`, `req.tls.eq:true`
- Always include the operator — `req.method.eq:"GET"`, not `req.method:"GET"`

## Namespaces

| Namespace | Description |
|---|---|
| `req` | All proxied HTTP requests |
| `resp` | All proxied HTTP responses |
| `row` | A request's numerical identifier in the traffic tables |
| `preset` | Filter presets (takes alias or name directly: `preset:"no-images"`) |
| `source` | Caido feature source — Search UI only, not usable via `caido_search` |

## Fields

### req

| Field | Description | Value Type |
|---|---|---|
| `created_at` | Date/time request was sent | Date/Time (RFC3339 / ISO8601 / RFC2822 / RFC7231 / ISO9075) |
| `ext` | Extension of the requested file | String/Byte — `eq`/`ne` need leading `.`: `req.ext.eq:".js"` |
| `body` | Request body only (no headers/line) | String/Byte |
| `header` | Request headers — three forms (see below) | String/Byte |
| `host` | Value of the request's `Host` header | String/Byte |
| `len` | Request size in bytes (line + headers + body) | Integer |
| `method` | HTTP method | String/Byte |
| `path` | URL path (includes files) | String/Byte |
| `port` | Target server port | Integer |
| `query` | URL query string (excludes leading `?`) | String/Byte |
| `raw` | Full raw request (line + headers + body) | String/Byte |
| `tls` | Whether connection used TLS | Boolean (`true`/`false`) |

### resp

| Field | Description | Value Type |
|---|---|---|
| `body` | Response body only (no headers) | String/Byte |
| `code` | Response status code | Integer |
| `header` | Response headers — three forms (see below) | String/Byte |
| `len` | Response size in bytes | Integer |
| `raw` | Full raw response | String/Byte |
| `roundtrip` | Total request/response cycle time (ms) | Integer |

### The `header` field (req and resp)

Three addressing forms, all taking the standard String/Byte operators:

```
req.header.name.eq:"Authorization"          # match header NAME
req.header.value.cont:"Bearer"              # search across all header VALUES
req.header["Authorization"].cont:"Bearer"   # address ONE header by name
resp.header["Set-Cookie"].cont:"HttpOnly"
```

### The `body` field (req and resp)

Body only — no request/response line, no headers:

```
req.body.regex:"password=[^&]+"
resp.body.cont:"stack trace"
```

### row

| Field | Description | Value Type |
|---|---|---|
| `id` | Traffic-table row identifier | Integer |

## Operators

| Operator | Description | Value Type | Notes |
|---|---|---|---|
| `eq` | Equal | String/Byte, Integer | Case sensitive; `ext` needs leading `.` |
| `ne` | Not equal | String/Byte, Integer | Case sensitive; `ext` needs leading `.` |
| `gt` | Greater than | Date/Time, Integer | |
| `gte` | Greater than or equal | Integer | |
| `lt` | Less than | Date/Time, Integer | |
| `lte` | Less than or equal | Integer | |
| `cont` | Contains | String/Byte | Case insensitive |
| `ncont` | Does not contain | String/Byte | Case insensitive |
| `like` | SQLite LIKE | String/Byte | `%` = zero+ chars, `_` = one char |
| `nlike` | SQLite NOT LIKE | String/Byte | |
| `regex` | Matches regex | String/Byte | Rust-flavored syntax; no look-ahead |
| `nregex` | Does not match regex | String/Byte | Rust-flavored |

## Usage notes

- **Negation** — use `ncont` / `nlike` / `ne` / `nregex` (there is no `NOT`).
- **Bodies and headers** — prefer the targeted fields over `raw`:
  `resp.body.cont:"error"` (body only), `req.header["Authorization"].cont:"Bearer"`
  (one header), `req.header.value.cont:"token"` (all header values).
  `req.raw.cont` / `resp.raw.cont` still work and match the whole message —
  use them when the section doesn't matter or you want line+headers+body in
  one sweep.
- **Status code** — the field is `resp.code` (`resp.code.gte:400`).
- **Case sensitivity** — `cont`/`ncont` are case-insensitive; `eq`/`ne`
  are case-sensitive.
- **File extensions** — `req.ext.eq:".js"` (leading dot required).
- **Regex** — Rust-flavored syntax; no look-ahead. Test at regex101.com
  with Rust syntax selected.

## Combining statements

- Logical operators: `AND`, `OR` (case-insensitive, same priority).
- Precedence: **`AND` binds tighter than `OR`**:
  - `A AND B OR C` ≡ `(A AND B) OR C`
  - `A OR B AND C` ≡ `A OR (B AND C)`
- Parenthesize for clarity: `(req.method.eq:"POST" OR req.method.eq:"PUT") AND resp.code.gte:400`
- Comments supported (single- and multi-line).

## Bare-string expansion (UI behavior)

Entering a bare string `"my value"` into the HTTPQL input is replaced at
runtime by:

```
(req.raw.cont:"my value" OR resp.raw.cont:"my value")
```

`caido_search` applies this expansion automatically for bare strings (and
repairs missing operators / unquoted values), reporting each rewrite in the
response's `httpql` block. Write the expansion explicitly in queries passed
to library functions (`create_filter`, `get_entry_requests`).

## Verified patterns

- Errors: `resp.code.gte:400 AND resp.code.lt:600`
- Slow responses: `resp.roundtrip.gt:5000`
- Large responses: `resp.len.gt:100000`
- JSON API traffic: `req.method.eq:"POST" AND req.raw.cont:"application/json"`
- Auth headers: `req.header.name.eq:"Authorization"` or `req.raw.cont:"Authorization"`
- Cookies in responses: `resp.header["Set-Cookie"].cont:"HttpOnly"`
- Tokens in bodies: `resp.body.cont:"eyJ"` (JWT prefix), `resp.body.regex:"AKIA[A-Z0-9]{16}"`
- Tokens in headers: `req.header.value.cont:"eyJ"`
- Stack traces: `resp.raw.cont:"Traceback" OR resp.raw.cont:"Exception"`
- Missing security header: `resp.raw.ncont:"Content-Security-Policy:"`
- Admin paths: `req.path.cont:"/admin" OR req.path.cont:"/wp-admin"`
- Open redirect: `req.query.cont:"redirect=" OR req.query.cont:"next="`
- Exposed files: `req.path.cont:".git" OR req.path.cont:".env"`
- Endpoints by extension: `req.ext.eq:".js" OR req.ext.eq:".json"`
- HTTPS only: `req.tls.eq:true`
- Regex on paths: `req.path.regex:"/v[0-9]"`

## Verified

Fields, operators, and patterns verified live against a Caido 0.58.x
instance via read-only `requests` queries (2026-09), including the
`header`/`body` fields added in v0.58.0.
