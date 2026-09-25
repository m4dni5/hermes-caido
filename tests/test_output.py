"""Tests for the bounded caido_get view (lib/output.py).

The contract under test: the parsed view is bounded — cookie values are
digested, header values capped, bodies truncated — while identity keys and
resolver notes survive; redact_cookies=False restores cookie values.
"""

from __future__ import annotations

import importlib

from conftest import _NS_PARENT, load_plugin

load_plugin()
output = importlib.import_module(f"{_NS_PARENT}.caido.lib.output")


RAW_REQUEST = (
    "POST /api/login?next=/home HTTP/1.1\r\n"
    "Host: app.example\r\n"
    "Cookie: session=aaaa1111; _ga=bbbb2222; tracking=cccc3333\r\n"
    "Authorization: Bearer token\r\n"
    "\r\n"
    '{"user": "admin"}'
)

RAW_RESPONSE = (
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: application/json\r\n"
    "Set-Cookie: session=zzzz; Path=/; HttpOnly; Secure; SameSite=Lax\r\n"
    "Set-Cookie: other=yyyy; Path=/api\r\n"
    "\r\n"
    '{"ok": true, "data": [1, 2, 3]}'
)

SAMPLE = {
    "id": "42",
    "host": "app.example",
    "port": 443,
    "method": "POST",
    "path": "/api/login",
    "query": "next=/home",
    "isTls": True,
    "createdAt": 1700000000000,
    "statusCode": 200,
    "roundtripTime": 120,
    "length": 27,
    "metadata": {"id": "7", "color": None},
    "metadata_id": "7",
    "requestRaw": RAW_REQUEST,
    "responseRaw": RAW_RESPONSE,
}


class TestParseRawHttp:
    def test_crlf(self):
        parsed = output.parse_raw_http(RAW_REQUEST)
        assert parsed["start_line"] == "POST /api/login?next=/home HTTP/1.1"
        assert {"name": "Host", "value": "app.example"} in parsed["headers"]
        assert parsed["body"] == '{"user": "admin"}'

    def test_bare_lf(self):
        raw = "GET / HTTP/1.1\nHost: x\n\nbody"
        parsed = output.parse_raw_http(raw)
        assert parsed["start_line"] == "GET / HTTP/1.1"
        assert parsed["headers"] == [{"name": "Host", "value": "x"}]
        assert parsed["body"] == "body"

    def test_empty(self):
        parsed = output.parse_raw_http(None)
        assert parsed == {"start_line": "", "headers": [], "body": ""}


class TestCookieDigest:
    def test_request_cookie_names_only(self):
        digested = output._digest_cookie("session=aaaa; _ga=bbbb; tracking=cccc")
        assert digested == "[3 cookies] session, _ga, tracking"
        assert "aaaa" not in digested

    def test_many_cookies_capped(self):
        value = "; ".join(f"c{i}=v{i}" for i in range(20))
        digested = output._digest_cookie(value)
        assert "[20 cookies]" in digested
        assert "(+8 more)" in digested

    def test_set_cookie_keeps_flags(self):
        digested = output._digest_set_cookie("session=zzzz; Path=/; HttpOnly; Secure")
        assert digested == "session=<redacted>; Path=/; HttpOnly; Secure"
        assert "zzzz" not in digested

    def test_set_cookie_no_attributes(self):
        assert output._digest_set_cookie("other=yyyy") == "other=<redacted>"


class TestRedactHeaders:
    def test_redact_default(self):
        headers, _ = output.redact_headers([{"name": "Cookie", "value": "a=1; b=2"}])
        assert headers[0]["value"] == "[2 cookies] a, b"

    def test_no_redact_keeps_values(self):
        headers, _ = output.redact_headers(
            [{"name": "Cookie", "value": "a=1; b=2"}], redact_cookies=False
        )
        assert headers[0]["value"] == "a=1; b=2"

    def test_no_redact_keeps_long_cookie_values_verbatim(self):
        # Regression: the generic oversized-header truncation must NOT
        # touch cookie values that were explicitly requested verbatim.
        long_cookie = "session=" + "x" * 6000
        headers, shortened = output.redact_headers(
            [{"name": "Cookie", "value": long_cookie}], redact_cookies=False
        )
        assert headers[0]["value"] == long_cookie
        assert not shortened

    def test_oversized_header_truncated(self):
        long_value = "x" * 1500
        headers, shortened = output.redact_headers([{"name": "X-Data", "value": long_value}])
        assert shortened
        assert len(headers[0]["value"]) < 1500
        assert "(+500 chars)" in headers[0]["value"]


class TestBuildGetView:
    def test_raws_replaced_by_parsed(self):
        view = output.build_get_view(SAMPLE)
        assert "requestRaw" not in view
        assert "responseRaw" not in view
        assert view["requestHeaders"] and view["responseHeaders"]

    def test_identity_and_resolver_keys_survive(self):
        view = output.build_get_view(SAMPLE)
        for key in ("id", "host", "method", "path", "query", "statusCode", "metadata_id"):
            assert key in view, key

    def test_cookie_values_digested_by_default(self):
        view = output.build_get_view(SAMPLE)
        cookie = next(h for h in view["requestHeaders"] if h["name"] == "Cookie")
        assert "aaaa1111" not in cookie["value"]
        assert "[3 cookies]" in cookie["value"]
        set_cookie = [h for h in view["responseHeaders"] if h["name"] == "Set-Cookie"]
        assert all("<redacted>" in h["value"] for h in set_cookie)
        assert "HttpOnly" in set_cookie[0]["value"]

    def test_redact_cookies_false_keeps_values(self):
        view = output.build_get_view(SAMPLE, redact_cookies=False)
        cookie = next(h for h in view["requestHeaders"] if h["name"] == "Cookie")
        assert "aaaa1111" in cookie["value"]

    def test_bodies_truncated_with_note(self):
        data = dict(SAMPLE, responseRaw=RAW_RESPONSE.replace('{"ok": true, "data": [1, 2, 3]}', "y" * 5000))
        view = output.build_get_view(data)
        assert len(view["responseBody"]) <= 2000 + len("... (truncated)")
        assert any("bodies truncated" in n for n in view["notes"])

    def test_notes_present_by_default(self):
        view = output.build_get_view(SAMPLE)
        assert any("redact_cookies=false" in n for n in view["notes"])


class TestBinaryBodyRawDecode:
    """Regression (bridge drive 2026-09): a binary body (e.g. deflate) must
    not push the whole raw message back to a base64 fallback — headers must
    still parse in the bounded view."""

    def test_binary_body_decodes_with_replacement(self):
        import base64 as b64
        http_requests = importlib.import_module(f"{_NS_PARENT}.caido.lib.graphql.http_requests")
        raw_bytes = b"POST /x HTTP/1.1\r\nHost: app.example\r\n\r\n" + b"\x9c\x02\x8b\x03binary"
        node = {"id": "1", "raw": b64.b64encode(raw_bytes).decode(), "response": None}
        mapped = http_requests._map_node(node)
        assert not mapped["requestRaw"].startswith("UE9TV")  # not base64
        parsed = output.parse_raw_http(mapped["requestRaw"])
        assert parsed["headers"] == [{"name": "Host", "value": "app.example"}]
        assert "\ufffd" in parsed["body"]

    def test_view_headers_present_for_binary_body(self):
        import base64 as b64
        http_requests = importlib.import_module(f"{_NS_PARENT}.caido.lib.graphql.http_requests")
        raw_bytes = b"GET /y HTTP/1.1\r\nCookie: a=1\r\n\r\n" + b"\x9c\x02"
        node = {"id": "2", "raw": b64.b64encode(raw_bytes).decode(), "response": None}
        mapped = http_requests._map_node(node)
        view = output.build_get_view(mapped)
        assert {"name": "Cookie", "value": "[1 cookies] a"} in view["requestHeaders"]


class TestCompactFormat:
    """Compact output must carry the context envelope and httpql repairs."""

    ENTRY = {
        "id": "10", "host": "app.example", "port": 443, "method": "GET",
        "path": "/x", "query": "", "isTls": True, "createdAt": 1700000000000,
        "statusCode": 200, "roundtripTime": 5, "length": 3,
        "metadata": {"id": "10", "color": None},
    }
    CTX = {
        "project": {"name": "proj", "id": "p1", "status": "open"},
        "active_scope": "2",
        "suggested_scope": {"id": "2", "name": "target", "matched_hosts": ["app.example"]},
        "recent_hosts": ["app.example", "cdn.example"],
    }

    def _format(self, data):
        tools = importlib.import_module(f"{_NS_PARENT}.caido.caido_tools")
        return tools._format(data, {"compact": True})

    def test_context_line_present(self):
        out = self._format({"entries": [self.ENTRY], "context": self.CTX})
        lines = out.split("\n")
        assert lines[0].startswith("context: project=proj")
        assert "active_scope=target (id 2" in lines[0]
        assert "app.example" in lines[0]
        assert lines[1] == "10 GET app.example/x [200] 3B 1700000000000"

    def test_context_none_set(self):
        ctx = dict(self.CTX, active_scope=None, suggested_scope=None)
        out = self._format({"entries": [self.ENTRY], "context": ctx})
        assert "active_scope=none" in out.split("\n")[0]

    def test_context_then_repairs_then_entries(self):
        out = self._format({
            "entries": [self.ENTRY],
            "context": self.CTX,
            "httpql": {"query": 'req.path.cont:"/x"', "repairs": ['req.path:"/x" → req.path.cont:"/x" (missing operator → cont)']},
        })
        lines = out.split("\n")
        assert lines[0].startswith("context:")
        assert lines[1].startswith("httpql repaired:")
        assert lines[2].startswith("10 GET ")

    def test_no_prefix_without_signals(self):
        out = self._format({"entries": [self.ENTRY]})
        assert out.split("\n") == ["10 GET app.example/x [200] 3B 1700000000000"]
