"""All 13 tool schemas survive the framework's schema sanitizer intact.

This is the regression test for the other hermes-tmux bug: a schema whose
``parameters`` used a top-level ``oneOf`` combinator was silently emptied
by the framework's ``sanitize_tool_schemas()`` (which strips top-level
combinators for strict-backend compat and injects an empty ``properties``
when none exists), so ``tool_describe`` returned nothing. Caido schemas
are plain ``properties``-based objects — this test proves none of them
get mangled.
"""

from __future__ import annotations

from conftest import _NS_PARENT, load_plugin
import sys  # noqa: E402

# Names of every registered tool, for the empty-properties exception.
ALLOWED_EMPTY = {"caido_onboard", "caido_health"}  # take no arguments


def _schemas():
    import importlib

    modname = f"{_NS_PARENT}.caido"
    importlib.import_module(f"{modname}.schemas")
    schemas_mod = sys.modules[f"{modname}.schemas"]
    return [
        getattr(schemas_mod, name)
        for name in dir(schemas_mod)
        if name.startswith("CAIDO_") and isinstance(getattr(schemas_mod, name), dict)
    ]


def _sanitize(schemas):
    from hermes_cli.tools_config import _get_platform_tools  # noqa: F401  # ensure importable path
    from tools.schema_sanitizer import sanitize_tool_schemas

    tools = [{"type": "function", "function": s} for s in schemas]
    out = sanitize_tool_schemas(tools)
    return [t["function"] for t in out]


def test_all_schemas_have_name_and_parameters():
    for s in _schemas():
        assert s.get("name"), f"schema missing name: {s}"
        assert "parameters" in s, f"{s.get('name')} missing parameters"


def test_no_top_level_combinators_in_schemas():
    """Schemas must not use top-level oneOf/anyOf/allOf — the sanitizer
    strips them and empties the schema."""
    for s in _schemas():
        params = s.get("parameters") or {}
        for banned in ("oneOf", "anyOf", "allOf"):
            assert banned not in params, (
                f"{s.get('name')} uses top-level {banned} — will be stripped by "
                "sanitize_tool_schemas and the schema will render empty"
            )


def test_sanitizer_preserves_properties_and_required():
    """After sanitization, every schema still exposes its properties and
    required fields (no empty-properties mangling)."""
    out = _sanitize(_schemas())
    assert len(out) == len(_schemas())
    for fn in out:
        name = fn.get("name")
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        if name in ALLOWED_EMPTY:
            continue
        assert props, f"{name} lost its properties to the sanitizer: {params}"
        # required fields must survive too
        assert "required" in params or not any(p.get("required") for p in _schemas() if p.get("name") == name), (
            f"{name} lost its required fields"
        )


def test_required_fields_survive():
    """Schemas that declare required fields keep them after sanitization."""
    out = _sanitize(_schemas())
    for fn in out:
        name = fn.get("name")
        orig = next((s for s in _schemas() if s.get("name") == name), None)
        if not orig:
            continue
        orig_required = (orig.get("parameters") or {}).get("required")
        if orig_required:
            got = (fn.get("parameters") or {}).get("required")
            assert got == orig_required, (
                f"{name} required changed: {orig_required} -> {got}"
            )
