# HTTPQL Reference — Caido query language

Authoritative source: https://docs.caido.io/app/reference/httpql
All statements below verified live against a Caido 0.57.x instance via
`caido_search` (2026-08) unless marked otherwise.

## Syntax

```
namespace.field.operator:value
```

- String values are **quoted**: `req.path.cont:"/admin"`
- Integers and booleans are **unquoted**: `resp.code.gte:400`, `req.tls.eq:true`
- Every clause needs an explicit operator — bare `req.method:"GET"` is **invalid**

## Namespaces

| Namespace | Description |
|---|---|
| `req` | All proxied HTTP requests |
| `resp` | All proxied HTTP responses |
| `row` | A request's numerical identifier in the traffic tables |
| `preset` | Filter presets (takes alias or name directly: `preset:"no-images"`) |
| `source` | Caido feature source (Search UI only — **returns nothing via `caido_search`**) |

## Fields

### req

| Field | Description | Value Type |
|---|---|---|
| `created_at` | Date/time request was sent | Date/Time (RFC3339 / ISO8601 / RFC2822 / RFC7231 / ISO9075) |
| `ext` | Extension of the requested file | String/Byte — `eq`/`ne` need leading `.`: `req.ext.eq:".js"` |
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
| `code` | Response status code | Integer |
| `len` | Response size in bytes | Integer |
| `raw` | Full raw response | String/Byte |
| `roundtrip` | Total request/response cycle time (ms) | Integer |

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

## Gotchas (verified)

1. **No `NOT` operator** — `NOT req.host.cont:"api"` fails with "Invalid
   HTTPQL query". Negate with `ncont` / `nlike` / `ne` / `nregex`.
2. **No body/header fields** — `req.body`, `resp.body`, `req.header.value`,
   `resp.header.value` do NOT exist. Search bodies/headers through
   `req.raw.cont` / `resp.raw.cont` with the literal substring.
3. **Status-code field is `resp.code`, not `resp.status`** — `resp.status.eq:200`
   is invalid.
4. **Bare `req.method:"GET"` is invalid** — always write the operator:
   `req.method.eq:"GET"`.
5. **`cont` is case-insensitive; `eq`/`ne` are case-sensitive.**
6. **`ext` needs the leading dot** — `req.ext.eq:".js"` (not `"js"`).
7. **Regex is Rust-flavored** — no look-ahead; test at regex101.com with
   Rust syntax selected.
8. **`source` namespace is Search-UI only** — via `caido_search` it returns
   nothing; don't rely on it.

## Combining statements

- Logical operators: `AND`, `OR` (case-insensitive, same priority).
- Precedence: **`AND` binds tighter than `OR`**:
  - `A AND B OR C` ≡ `(A AND B) OR C`
  - `A OR B AND C` ≡ `A OR (B AND C)`
- Use parentheses for clarity: `(req.method.eq:"POST" OR req.method.eq:"PUT") AND resp.code.gte:400`
- Comments supported (single- and multi-line) — useful to temporarily
  disable clauses.

## Bare-string expansion (UI behavior)

Entering a bare string `"my value"` into the HTTPQL input is replaced at
runtime by:

```
(req.raw.cont:"my value" OR resp.raw.cont:"my value")
```

Write the expansion explicitly in `caido_search` queries.

## Verified patterns

- Errors: `resp.code.gte:400 AND resp.code.lt:600`
- Slow responses: `resp.roundtrip.gt:5000`
- Large responses: `resp.len.gt:100000`
- JSON API traffic: `req.method.eq:"POST" AND req.raw.cont:"application/json"`
- Auth headers: `req.raw.cont:"Authorization"` (case-insensitive `cont`
  matches the header name)
- Tokens: `resp.raw.cont:"eyJ"` (JWT prefix), `resp.raw.cont:"AKIA"` (AWS key)
- Stack traces: `resp.raw.cont:"Traceback" OR resp.raw.cont:"Exception"`
- Missing security header: `resp.raw.ncont:"Content-Security-Policy:"`
- Admin paths: `req.path.cont:"/admin" OR req.path.cont:"/wp-admin"`
- Open redirect: `req.query.cont:"redirect=" OR req.query.cont:"next="`
- Exposed files: `req.path.cont:".git" OR req.path.cont:".env"`
- Endpoints by extension: `req.ext.eq:".js" OR req.ext.eq:".json"`
- HTTPS only: `req.tls.eq:true`
- Regex on paths: `req.path.regex:"/v[0-9]"`

## Third-party cheatsheet — caveats

`rikosec/httpql-cheatsheet` (https://github.com/rikosec/httpql-cheatsheet)
is a good browserable library of bug-bounty query patterns, but its syntax
has errors against the current schema:

- Uses `NOT` — invalid; use `ncont`/`nlike`/`ne`/`nregex`
- Uses `resp.status` — should be `resp.code`
- Uses bare `req.method:"GET"` — needs `.eq`
- Uses `req.body`/`resp.body` fields — don't exist; use `req.raw`/`resp.raw`
