"""Caido findings operations — sync wrappers.

Usage:
    import findings
    results = findings.list_findings()
    detail = findings.get_finding(finding_id="1")
"""

from __future__ import annotations
from sync import sync_run
from graphql.findings import (
    list_findings as _list_findings,
    get_finding as _get_finding,
    create_finding as _create_finding,
    update_finding as _update_finding,
)


def list_findings(query: str | None = None, limit: int = 50) -> dict:
    """List findings. Optional title filter."""
    return sync_run(_list_findings, query=query, limit=limit)


def get_finding(finding_id: str) -> dict:
    """Get a finding by ID."""
    return sync_run(_get_finding, finding_id=finding_id)


def create_finding(
    title: str,
    description: str | None = None,
    severity: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Create a finding."""
    return sync_run(_create_finding, title=title, description=description, severity=severity, request_id=request_id)


def update_finding(
    finding_id: str,
    title: str | None = None,
    description: str | None = None,
    severity: str | None = None,
) -> dict:
    """Update a finding."""
    return sync_run(_update_finding, finding_id=finding_id, title=title, description=description, severity=severity)
