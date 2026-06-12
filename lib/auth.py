"""Caido auth and setup — sync wrappers.

Usage:
    import auth
    status = auth.auth_status()
    auth.clear_cache()
"""

from __future__ import annotations
from sync import sync_run
from graphql.auth import (
    auth_status as _auth_status,
    clear_cache as _clear_cache,
    test_connection as _test_connection,
    setup as _setup,
)


def auth_status() -> dict:
    """Check current auth state."""
    return sync_run(_auth_status)


def clear_cache() -> dict:
    """Clear cached tokens and force re-auth."""
    return sync_run(_clear_cache)


def test_connection() -> dict:
    """Test Caido connectivity and auth."""
    return sync_run(_test_connection)


def setup(pat: str | None = None, url: str | None = None) -> dict:
    """Configure credentials."""
    return sync_run(_setup, pat=pat, url=url)
