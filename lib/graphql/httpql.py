"""HTTPQL shorthand normalization — repair before reject.

Caido's HTTPQL parser is strict: the operator is never optional
(``req.path.cont:"/x"``, never ``req.path:"/x"``), string values must be
double-quoted, and the UI's bare-string expansion does not exist
server-side. Agents reliably write the shorthand anyway, so ``search()``
runs every query through :func:`normalize_httpql` first and reports the
rewrites in the response's ``httpql`` block.

Contract: only forms that would fail anyway are touched. A query the
server accepts passes through byte-identical (verify with the tests —
``normalize_httpql(valid) == valid``).

Repair rules:
- missing operator → ``cont`` on string fields (case-insensitive substring,
  a superset of ``eq`` so nothing is silently missed), ``eq`` on
  integer/boolean fields
- unquoted or single-quoted string values → double-quoted; quoted numbers/
  booleans on integer/boolean fields → unquoted
- bare strings (``graphql``, ``"my value"``) → the Caido UI expansion
  ``(req.raw.cont:"v" OR resp.raw.cont:"v")``
- everything else (``preset:"x"``, date fields, unknown fields) is left
  untouched — the error hint guides those.
"""

from __future__ import annotations

import re

SYNTAX_HINT = (
    "HTTPQL syntax is namespace.field.operator:value — the operator is REQUIRED "
    '(req.path.cont:"/x", not req.path:"/x"), string values are double-quoted '
    '(req.method.eq:"GET", not req.method.eq:GET), and negation uses '
    "ne/ncont/nlike/nregex. Full reference: "
    'skill_view("caido:caido", "references/httpql.md").'
)

_OPERATORS = frozenset({
    "eq", "ne", "gt", "gte", "lt", "lte",
    "cont", "ncont", "like", "nlike", "regex", "nregex",
})
_KEYWORDS = frozenset({"AND", "OR", "NOT"})

_INT_FIELDS = frozenset({
    "req.port", "req.len", "resp.code", "resp.len", "resp.roundtrip", "row.id",
})
_BOOL_FIELDS = frozenset({"req.tls"})
_STR_FIELDS = frozenset({
    "req.path", "req.host", "req.method", "req.query", "req.ext",
    "req.raw", "req.body", "req.header", "req.header.name", "req.header.value",
    "resp.raw", "resp.body", "resp.header", "resp.header.name", "resp.header.value",
})


def _field_type(key: str) -> str | None:
    """Type of a field path (operator and [".."] bracket already removed)."""
    if key in _INT_FIELDS:
        return "int"
    if key in _BOOL_FIELDS:
        return "bool"
    if key in _STR_FIELDS:
        return "str"
    return None  # dates, preset, unknown fields — leave untouched


def _tokenize(q: str) -> list[tuple[str, str, str]]:
    """Split into (kind, text, quote) tokens.

    Kinds: ws, paren, colon, word, str, comment. Words swallow [".."]
    bracket runs so ``req.header["X-Y"]`` stays one token. ``//`` and
    ``/* */`` comments are captured whole and passed through verbatim.
    """
    tokens: list[tuple[str, str, str]] = []
    i, n = 0, len(q)
    while i < n:
        c = q[i]
        if c.isspace():
            j = i
            while j < n and q[j].isspace():
                j += 1
            tokens.append(("ws", q[i:j], ""))
            i = j
        elif c in "()":
            tokens.append(("paren", c, ""))
            i += 1
        elif c == ":":
            tokens.append(("colon", ":", ""))
            i += 1
        elif c in "\"'":
            j = i + 1
            while j < n and q[j] != c:
                j += 1
            tokens.append(("str", q[i + 1:j], c))
            i = min(j + 1, n)
        elif q.startswith("//", i):
            j = q.find("\n", i)
            j = n if j == -1 else j
            tokens.append(("comment", q[i:j], ""))
            i = j
        elif q.startswith("/*", i):
            end = q.find("*/", i)
            j = n if end == -1 else end + 2
            tokens.append(("comment", q[i:j], ""))
            i = j
        else:
            j = i
            while j < n:
                cj = q[j]
                if cj.isspace() or cj in "():" or cj in "\"'":
                    break
                if cj == "[":
                    k = q.find("]", j)
                    j = n if k == -1 else k + 1
                    continue
                if q.startswith("//", j) or q.startswith("/*", j):
                    break
                j += 1
            if j == i:  # never stall on pathological input
                j = i + 1
            tokens.append(("word", q[i:j], ""))
            i = j
    return tokens


def _expand_bare(text: str, quote: str, repairs: list[str]) -> str:
    if not quote and text.upper() in _KEYWORDS:
        return text
    expanded = f'(req.raw.cont:"{text}" OR resp.raw.cont:"{text}")'
    shown = f"{quote}{text}{quote}" if quote else text
    repairs.append(f"{shown} → {expanded} (bare string expanded, Caido UI behavior)")
    return expanded


def _predicate(word: str, value: tuple[str, str, str], repairs: list[str]) -> str:
    """Repair one ``field[.op]:value`` predicate; return it re-emitted."""
    vkind, vtext, vquote = value
    val_repr = f"{vquote}{vtext}{vquote}" if vkind == "str" else vtext
    original = f"{word}:{val_repr}"

    base = re.sub(r"\[[^\]]*\]", "", word)
    segs = base.split(".")
    has_op = segs[-1] in _OPERATORS
    key = ".".join(segs[:-1]) if has_op else base
    ftype = _field_type(key)
    if ftype is None:
        return original  # unknown/date/preset — the error hint guides these

    new_word = word
    reasons: list[str] = []
    if not has_op:
        op = "cont" if ftype == "str" else "eq"
        new_word = f"{word}.{op}"
        reasons.append(f"missing operator → {op}")

    # Value representation: strings double-quoted, ints/bools bare.
    if ftype == "str":
        new_val = f'"{vtext}"'
        vreason = "value double-quoted"
    elif ftype == "int":
        if not vtext.isdigit():
            return original  # not a number — don't turn garbage into garbage
        new_val = vtext
        vreason = "value unquoted"
    else:  # bool
        if vtext.lower() not in ("true", "false"):
            return original
        new_val = vtext.lower()
        vreason = "value unquoted"
    if new_val != val_repr:
        reasons.append(vreason)

    new = f"{new_word}:{new_val}"
    if new != original:
        repairs.append(f"{original} → {new} ({'; '.join(reasons)})")
    return new


def normalize_httpql(query: str) -> tuple[str, list[str]]:
    """Repair common shorthand in an HTTPQL query.

    Returns ``(normalized_query, repairs)`` where ``repairs`` is a list of
    human-readable "before → after (reason)" notes — empty when the query
    passed through unchanged.
    """
    toks = _tokenize(query)
    out: list[str] = []
    repairs: list[str] = []
    i, n = 0, len(toks)
    while i < n:
        kind, text, quote = toks[i]
        if kind in ("ws", "paren", "colon", "comment"):
            out.append(text)
            i += 1
            continue
        if kind == "str":
            out.append(_expand_bare(text, quote, repairs))
            i += 1
            continue
        # word: a predicate when followed by :value, else a bare string
        j = i + 1
        if (
            j < n and toks[j][0] == "colon"
            and j + 1 < n and toks[j + 1][0] in ("str", "word")
        ):
            out.append(_predicate(text, (toks[j + 1][0], toks[j + 1][1], toks[j + 1][2]), repairs))
            i = j + 2
            continue
        if toks[i][0] == "word" and j < n and toks[j][0] == "colon":
            # colon with no parseable value — emit verbatim, don't expand
            out.append(text)
            i += 1
            continue
        out.append(_expand_bare(text, "", repairs))
        i += 1

    normalized = "".join(out)
    if normalized != query and not repairs:
        repairs.append("formatting normalized")
    return normalized, repairs
