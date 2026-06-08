"""Finding operations for the Caido Python SDK CLI.

Wraps the Caido SDK ``FindingSDK`` for listing, retrieving, creating, and
updating security findings.  Every public async function accepts an optional
``client`` keyword; when omitted a shared client is obtained from
``lib.client``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from client import get_client  # noqa: E402


# ---------------------------------------------------------------------------
# SDK-object → plain-dict conversion
# ---------------------------------------------------------------------------

def map_finding(node: Any) -> dict[str, Any]:
    """Convert an SDK ``Finding`` dataclass to a plain dict.

    The returned dict uses camelCase keys for JSON serialisation.
    """
    return {
        "id":           str(node.id),
        "requestId":    str(node.request_id) if node.request_id else None,
        "title":        node.title,
        "reporter":     node.reporter,
        "description":  node.description,
        "dedupeKey":    node.dedupe_key,
        "host":         node.host,
        "path":         node.path,
        "hidden":       node.hidden,
        "createdAt":    node.created_at.isoformat() if node.created_at else None,
    }


def _compact_finding(d: dict[str, Any]) -> dict[str, Any]:
    """Return a slim dict suitable for list views."""
    return {
        "id":          d["id"],
        "title":       d["title"],
        "reporter":    d["reporter"],
        "host":        d["host"],
        "path":        d["path"],
        "hidden":      d["hidden"],
        "createdAt":   d["createdAt"],
    }


# ---------------------------------------------------------------------------
# Public async helpers
# ---------------------------------------------------------------------------

async def list_findings(
    query: str | None = None,
    limit: int = 50,
    client: Any | None = None,
) -> dict[str, Any]:
    """List findings, optionally filtered by a title substring.

    Parameters
    ----------
    query:
        Optional substring to match against finding titles (case-insensitive).
    limit:
        Maximum number of findings to return (default 50).
    client:
        Optional pre-connected SDK ``Client``.

    Returns
    -------
    dict
        ``{"findings": [...], "total": N}`` on success or
        ``{"error": "...", "findings": [], "total": 0}`` on failure.
    """
    try:
        c = client or await get_client()
        connection = await c.findings.list().first(limit)

        entries = [_compact_finding(map_finding(edge.node)) for edge in connection.edges]

        # Client-side title filter when a query is provided
        if query:
            q = query.lower()
            entries = [e for e in entries if q in (e.get("title") or "").lower()]

        return {"findings": entries, "total": len(entries)}
    except Exception as exc:
        return {"error": str(exc), "findings": [], "total": 0}


async def get_finding(
    finding_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    """Fetch a single finding by ID.

    Returns the full finding dict or an ``{"error": "..."}`` dict.
    """
    try:
        c = client or await get_client()
        node = await c.findings.get(finding_id)
        if node is None:
            return {"error": f"Finding {finding_id!r} not found"}
        return map_finding(node)
    except Exception as exc:
        return {"error": str(exc)}


async def create_finding(
    title: str,
    description: str,
    severity: str = "info",
    request_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Create a new finding.

    Parameters
    ----------
    title:
        Short summary of the finding.
    description:
        Detailed description (severity info is prepended when non-default).
    severity:
        Severity label (``critical``, ``high``, ``medium``, ``low``, ``info``).
        Stored in the description since the SDK does not expose a dedicated
        severity field.
    request_id:
        Optional associated request ID.  A placeholder is used when omitted.
    client:
        Optional pre-connected SDK ``Client``.

    Returns
    -------
    dict
        The created finding or ``{"error": "..."}``.
    """
    try:
        from caido_sdk_client.types.finding import CreateFindingOptions

        c = client or await get_client()

        # Prepend severity to description so it is not lost
        full_description = f"[{severity.upper()}] {description}" if severity and severity != "info" else description

        options = CreateFindingOptions(
            title=title,
            reporter="caido-py",
            description=full_description,
        )

        rid = request_id or "0"
        node = await c.findings.create(rid, options)
        return map_finding(node)
    except Exception as exc:
        return {"error": str(exc)}


async def update_finding(
    finding_id: str,
    title: str | None = None,
    description: str | None = None,
    severity: str | None = None,
    state: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Update an existing finding.

    Only the fields that are provided (non-``None``) are changed.  The SDK
    ``UpdateFindingOptions`` requires all three fields (``title``,
    ``description``, ``hidden``), so missing values are filled from the
    current finding first.

    Parameters
    ----------
    finding_id:
        ID of the finding to update.
    title:
        New title (or ``None`` to keep current).
    description:
        New description (or ``None`` to keep current).
    severity:
        New severity label — prepended to description.
    state:
        ``"hidden"`` to hide the finding, ``"visible"`` to un-hide.
        Maps to the SDK ``hidden`` boolean field.
    client:
        Optional pre-connected SDK ``Client``.

    Returns
    -------
    dict
        The updated finding or ``{"error": "..."}``.
    """
    try:
        from caido_sdk_client.types.finding import UpdateFindingOptions

        c = client or await get_client()

        # Fetch current finding to fill in unchanged fields
        current = await c.findings.get(finding_id)
        if current is None:
            return {"error": f"Finding {finding_id!r} not found"}

        # Resolve effective values
        eff_title = title if title is not None else current.title
        eff_description = description if description is not None else (current.description or "")
        eff_hidden = current.hidden

        # Apply severity into description
        if severity is not None:
            # Strip existing severity tag if present
            desc_text = eff_description
            if desc_text.startswith("[") and "] " in desc_text[:20]:
                desc_text = desc_text.split("] ", 1)[1]
            eff_description = f"[{severity.upper()}] {desc_text}" if severity != "info" else desc_text

        # Map state to hidden flag
        if state is not None:
            eff_hidden = state.lower() == "hidden"

        options = UpdateFindingOptions(
            title=eff_title,
            description=eff_description,
            hidden=eff_hidden,
        )

        node = await c.findings.update(finding_id, options)
        return map_finding(node)
    except Exception as exc:
        return {"error": str(exc)}
