"""Pin-tests for the auth subprocess path (ares bugs, 2026-10-26).

Both shipped invisible: ``import sys`` was missing from caido_tools.py, so
``caido_auth_setup`` died with ``NameError: sys`` — py_compile and the
sanitizer suite never exercise ``_setup_via_subprocess``. And the
device-flow cloud calls choked on api.caido.io's brotli replies (served
even when the client does not advertise compression), killing the auth
flow with ``Can not decode content-encoding: br``. Pinned here so neither
regresses silently again.
"""

from __future__ import annotations

import importlib
import inspect

from conftest import _NS_PARENT, load_plugin


def _caido_tools():
    load_plugin()  # set up the hermes_plugins_test namespace before importing
    return importlib.import_module(f"{_NS_PARENT}.caido.caido_tools")


def _client():
    load_plugin()
    return importlib.import_module(f"{_NS_PARENT}.caido.lib.graphql.client")


def test_setup_via_subprocess_names_resolve():
    """Every module-level name the auth helper loads must resolve.

    Regression: caido_tools.py used ``sys.executable`` without importing
    ``sys`` — NameError surfaced only when caido_auth_setup actually ran.
    """
    mod = _caido_tools()
    for name in ("sys", "os", "asyncio", "_subprocess", "json", "Path"):
        assert hasattr(mod, name), f"caido_tools is missing module-level name: {name}"
    assert mod.sys.executable, "sys.executable did not resolve"


def test_cloud_device_flow_requests_identity_encoding():
    """api.caido.io serves Content-Encoding: br even to plain requests.

    Both device-flow cloud calls must ask for identity encoding, or any
    aiohttp build without brotli decoding dies on the reply (ares bug
    2026-10-26).
    """
    client = _client()
    info_src = inspect.getsource(client._get_device_information)
    approve_src = inspect.getsource(client._approve_via_cloud)
    assert '"Accept-Encoding": "identity"' in info_src, (
        "_get_device_information must send Accept-Encoding: identity"
    )
    assert '"Accept-Encoding": "identity"' in approve_src, (
        "_approve_via_cloud must send Accept-Encoding: identity"
    )
