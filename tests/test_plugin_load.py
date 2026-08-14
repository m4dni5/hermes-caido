"""The plugin loads under the framework loader and registers all 13 tools.

This is the regression test for the class of bug that broke hermes-tmux:
a plugin that imports fine when launched from inside its directory but
fails with ``No module named 'schemas'`` under the framework loader
(which imports ``__init__.py`` as a namespaced package and never puts
the plugin dir on ``sys.path``). Caido uses package-relative imports, so
it should load from any cwd — this test proves it.
"""

from __future__ import annotations

from conftest import PLUGIN_DIR, _NS_PARENT, load_plugin
import sys  # noqa: E402


class FakeCtx:
    """Minimal PluginContext that records tool registrations."""

    def __init__(self) -> None:
        self.tools: list[dict] = []
        self.commands: list[dict] = []
        self.skills: list[tuple] = []

    def register_tool(self, **kwargs) -> None:
        self.tools.append(kwargs)

    def register_command(self, name, handler, **kwargs) -> None:
        self.commands.append({"name": name, "handler": handler, **kwargs})

    def register_skill(self, name, path) -> None:
        self.skills.append((name, path))

    @property
    def manifest(self):
        class M:
            path = str(PLUGIN_DIR)
        return M()


def test_plugin_registers_13_tools(plugin) -> None:
    """register() wires all 13 tools."""
    ctx = FakeCtx()
    plugin.register(ctx)
    assert len(ctx.tools) == 13, f"expected 13 tools, got {len(ctx.tools)}"


def test_manifest_tools_covered_by_registration(plugin) -> None:
    """Every tool in plugin.yaml's provides_tools is registered."""
    import yaml  # type: ignore

    manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text())
    provided = set(manifest.get("provides_tools", []))
    ctx = FakeCtx()
    plugin.register(ctx)
    registered = {t["name"] for t in ctx.tools}
    missing = provided - registered
    assert not missing, f"plugin.yaml lists tools not registered: {missing}"


def test_sync_wrappers_import_within_package(plugin) -> None:
    """The lib sync wrappers import cleanly as package members.

    This catches the import-strategy regression (bare ``import sync`` /
    ``import graphql`` after a ``sys.path.insert``) that can break under
    the loader or collide with stdlib/third-party module names.
    """
    import importlib

    modname = f"{_NS_PARENT}.caido"
    for sub in [
        "lib.sync",
        "lib.http_requests",
        "lib.findings",
        "lib.replay",
        "lib.management",
        "lib.automate",
        "lib.auth",
        "lib.placeholders",
        "lib.payloads",
    ]:
        importlib.import_module(f"{modname}.{sub}")
    # smoke: the sync wrapper functions are callable
    http = sys.modules[f"{modname}.lib.http_requests"]
    assert callable(http.search)
    assert callable(http.get)


def test_no_syspath_insert_in_framework_path() -> None:
    """caido_tools.py must not mutate global sys.path.

    This is the anti-pattern we removed: a top-of-module ``sys.path.insert``
    that pollutes the shared process and relies on generic module names
    (``graphql``, ``output``). If it regresses, this test fails.

    The check targets actual statements, not prose: comments and docstrings
    are stripped with the tokenizer before scanning, so the warning text in
    the header comment doesn't trip the assertion.
    """
    import io
    import tokenize

    src = (PLUGIN_DIR / "caido_tools.py").read_text()

    code_lines = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.NL):
            continue
        code_lines.append(tok.line)
    code = "\n".join(code_lines)

    assert "sys.path.insert" not in code
    assert "from graphql" not in code
    assert "from output" not in code
