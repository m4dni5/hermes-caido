"""Pin-tests for the auth subprocess path (ares bugs, 2026-10-26).

All shipped invisible: ``import sys`` was missing from caido_tools.py, so
``caido_auth_setup`` died with ``NameError: sys`` — py_compile and the
sanitizer suite never exercise ``_setup_via_subprocess``. The device-flow
cloud calls choked on api.caido.io's brotli replies (served even when the
client does not advertise compression), killing the auth flow with
``Can not decode content-encoding: br``. And the gateway keeps profile
secrets out of ``os.environ`` (secret scope), so the auth tool must fall
back to the profile ``.env`` resolvers to self-serve in-session. Pinned
here so none regress silently again.
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


def test_handle_auth_setup_falls_back_to_env_file_resolvers():
    """The auth tool must self-serve creds from the profile .env.

    The gateway keeps profile secrets OUT of os.environ (secret scope), so
    args/env alone leave caido_auth_setup unable to run in-session — it
    must fall back to _resolve_pat()/_resolve_url() (2026-10-26).
    """
    mod = _caido_tools()
    src = inspect.getsource(mod.handle_auth_setup)
    assert "_resolve_pat()" in src, "handle_auth_setup must fall back to _resolve_pat()"
    assert "_resolve_url()" in src, "handle_auth_setup must fall back to _resolve_url()"


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
