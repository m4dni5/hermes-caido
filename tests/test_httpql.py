"""Tests for HTTPQL shorthand normalization (lib/graphql/httpql.py).

The contract under test: forms the server rejects get repaired, forms the
server accepts pass through byte-identical. The repairs mirror live probes
against a Caido 0.58.x instance (2026-09): ``field:"v"`` (missing
operator), ``field:400`` / ``field:true`` (missing operator on non-string
fields), unquoted/single-quoted string values, and bare strings all fail
server-side; every dot-form with an operator parses.
"""

from __future__ import annotations

import importlib

from conftest import _NS_PARENT, load_plugin

load_plugin()
httpql = importlib.import_module(f"{_NS_PARENT}.caido.lib.graphql.httpql")


def norm(q: str) -> tuple[str, list[str]]:
    return httpql.normalize_httpql(q)


class TestValidQueriesUntouched:
    """Queries the server accepts must pass through byte-identical."""

    def test_full_dot_form(self):
        q = 'req.path.cont:"/graphql"'
        assert norm(q) == (q, [])

    def test_compound_expression(self):
        q = 'req.method.eq:"GET" AND req.path.cont:"/graphql"'
        assert norm(q) == (q, [])

    def test_numeric_and_bool_operators(self):
        q = "resp.code.gte:400 AND resp.code.lt:600 AND req.tls.eq:true"
        assert norm(q) == (q, [])

    def test_or_with_parens(self):
        q = '(req.method.eq:"POST" OR req.method.eq:"PUT") AND resp.code.gte:400'
        assert norm(q) == (q, [])

    def test_bracket_header_form(self):
        q = 'req.header["Cookie"].cont:"session"'
        assert norm(q) == (q, [])

    def test_preset_special_form(self):
        q = 'preset:"no-images"'
        assert norm(q) == (q, [])

    def test_negation_operators(self):
        q = 'resp.raw.ncont:"Content-Security-Policy:" AND req.ext.ne:".png"'
        assert norm(q) == (q, [])

    def test_regex_and_like(self):
        q = 'req.path.regex:"/v[0-9]" AND req.query.like:"id=%"'
        assert norm(q) == (q, [])

    def test_date_predicate_untouched(self):
        q = 'req.created_at.gt:"2026-01-01"'
        assert norm(q) == (q, [])

    def test_comments_pass_through(self):
        q = 'req.path.cont:"/x" // find admin\n AND resp.code.eq:200'
        assert norm(q) == (q, [])

    def test_idempotent_on_repaired_output(self):
        for q in (
            'req.path:"/graphql"',
            "graphql",
            "req.method.eq:GET",
            'resp.code:400',
        ):
            once, _ = norm(q)
            twice, repairs = norm(once)
            assert twice == once
            assert repairs == []


class TestMissingOperator:
    def test_string_field_gets_cont(self):
        out, repairs = norm('req.path:"/graphql"')
        assert out == 'req.path.cont:"/graphql"'
        assert len(repairs) == 1 and "missing operator → cont" in repairs[0]

    def test_method_missing_operator(self):
        out, _ = norm('req.method:"GET"')
        assert out == 'req.method.cont:"GET"'

    def test_header_bracket_missing_operator(self):
        out, _ = norm('req.header["Cookie"]:"session"')
        assert out == 'req.header["Cookie"].cont:"session"'

    def test_header_value_missing_operator(self):
        out, _ = norm('req.header.value:"token"')
        assert out == 'req.header.value.cont:"token"'

    def test_int_field_gets_eq(self):
        out, repairs = norm("resp.code:400")
        assert out == "resp.code.eq:400"
        assert "missing operator → eq" in repairs[0]

    def test_bool_field_gets_eq(self):
        out, _ = norm("req.tls:true")
        assert out == "req.tls.eq:true"

    def test_unknown_field_left_untouched(self):
        q = 'req.bogus:"x"'
        assert norm(q) == (q, [])

    def test_unknown_field_with_fake_operator_untouched(self):
        q = 'req.path.contains:"/x"'
        assert norm(q) == (q, [])

    def test_int_field_non_numeric_value_untouched(self):
        q = "resp.code:>=400"
        assert norm(q) == (q, [])


class TestValueQuoting:
    def test_unquoted_string_value(self):
        out, repairs = norm("req.method.eq:GET")
        assert out == 'req.method.eq:"GET"'
        assert "value double-quoted" in repairs[0]

    def test_single_quoted_value(self):
        out, _ = norm("req.path.cont:'/graphql'")
        assert out == 'req.path.cont:"/graphql"'

    def test_quoted_number_on_int_field_unquoted(self):
        out, _ = norm('resp.code.eq:"400"')
        assert out == "resp.code.eq:400"

    def test_quoted_bool_on_bool_field_unquoted(self):
        out, _ = norm('req.tls.eq:"true"')
        assert out == "req.tls.eq:true"

    def test_missing_operator_and_quoting_combined(self):
        out, repairs = norm("req.path:/graphql")
        assert out == 'req.path.cont:"/graphql"'
        assert len(repairs) == 1
        assert "missing operator" in repairs[0] and "quoted" in repairs[0]


class TestBareStringExpansion:
    def test_bare_word(self):
        out, repairs = norm("graphql")
        assert out == '(req.raw.cont:"graphql" OR resp.raw.cont:"graphql")'
        assert "bare string expanded" in repairs[0]

    def test_bare_quoted_string(self):
        out, _ = norm('"/graphql"')
        assert out == '(req.raw.cont:"/graphql" OR resp.raw.cont:"/graphql")'

    def test_keywords_pass_through(self):
        q = 'req.path.cont:"/a" AND resp.code.eq:200 OR req.host.eq:"x"'
        assert norm(q) == (q, [])

    def test_bare_string_next_to_predicate(self):
        out, _ = norm('req.method.eq:"GET" AND trace')
        assert 'req.method.eq:"GET" AND ' in out
        assert '(req.raw.cont:"trace" OR resp.raw.cont:"trace")' in out
