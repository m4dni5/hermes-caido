"""Pytest fixtures for the hermes-caido test suite.

The plugin is a flat directory plugin. The framework loader imports its
``__init__.py`` as a namespaced package (``hermes_plugins.caido``) with
``__path__`` set to the plugin dir, where relative imports resolve. The
tests reproduce that loader so imports behave exactly as they do in
production — they do NOT add the plugin dir to the top of ``sys.path``
and import top-level modules, because ``caido_tools.py`` and the
``lib/*`` sync wrappers use package-relative imports that only resolve
inside the package.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from typing import Iterator

import pytest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
_NS_PARENT = "hermes_plugins_test"


def load_plugin() -> types.ModuleType:
    """Load the plugin under the framework loader's import semantics."""
    init_file = PLUGIN_DIR / "__init__.py"

    # Neutralize the plugin dir on sys.path so we prove package-relative
    # imports work without it (the loader does not put it there).
    sys.path = [p for p in sys.path if "hermes-caido" not in p]

    if _NS_PARENT not in sys.modules:
        ns = types.ModuleType(_NS_PARENT)
        ns.__path__ = []
        ns.__package__ = _NS_PARENT
        sys.modules[_NS_PARENT] = ns

    modname = f"{_NS_PARENT}.caido"
    if modname in sys.modules:
        del sys.modules[modname]
    for k in [k for k in sys.modules if k.startswith(modname)]:
        del sys.modules[k]

    spec = importlib.util.spec_from_file_location(
        modname, init_file, submodule_search_locations=[str(PLUGIN_DIR)]
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = modname
    module.__path__ = [str(PLUGIN_DIR)]
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plugin() -> Iterator[types.ModuleType]:
    """The plugin module, loaded under framework-loader import semantics."""
    yield load_plugin()


@pytest.fixture(scope="module")
def schemas_module():
    """The schemas module, imported as part of the plugin package."""
    plugin = load_plugin()
    return sys.modules[f"{_NS_PARENT}.caido.schemas"]
