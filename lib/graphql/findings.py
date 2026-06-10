"""Caido Findings management via GraphQL."""

import sys
from pathlib import Path

from .client import graphql

# ── GraphQL fragments & queries ─────────────────────────────────────────────

FINDING_FRAGMENT = """
fragment FindingFull on Finding {
  id
  request { id }
  title
  reporter
  description
  dedupeKey
  host
  path
  hidden
  createdAt
}
"""

FINDINGS_QUERY = """
query Findings($first: Int, $after: String, $last: Int, $before: String, $filter: FilterClauseFindingInput, $order: FindingOrderInput) {
  findings(first: $first, after: $after, last: $last, before: $before, filter: $filter, order: $order) {
    edges {
      cursor
      node { ...FindingFull }
    }
    pageInfo { hasNextPage hasPreviousPage startCursor endCursor }
  }
}
""" + FINDING_FRAGMENT

GET_FINDING_QUERY = """
query Finding($id: ID!) {
  finding(id: $id) { ...FindingFull }
}
""" + FINDING_FRAGMENT

CREATE_FINDING_MUTATION = """
mutation CreateFinding($requestId: ID!, $input: CreateFindingInput!) {
  createFinding(requestId: $requestId, input: $input) {
    error {
      __typename
      ... on OtherUserError { code }
      ... on UnknownIdUserError { code }
    }
    finding { ...FindingFull }
  }
}
""" + FINDING_FRAGMENT

UPDATE_FINDING_MUTATION = """
mutation UpdateFinding($id: ID!, $input: UpdateFindingInput!) {
  updateFinding(id: $id, input: $input) {
    error {
      __typename
      ... on UnknownIdUserError { code }
      ... on OtherUserError { code }
    }
    finding { ...FindingFull }
  }
}
""" + FINDING_FRAGMENT


# ── Public API ───────────────────────────────────────────────────────────────

async def list_findings(query=None, limit=50, client=None):
    """List findings. If *query* is given, filter client-side by title."""
    data = await graphql(
        FINDINGS_QUERY,
        variables={"first": limit},

    )
    edges = data.get("findings", {}).get("edges", [])
    findings = [e["node"] for e in edges if e.get("node")]

    if query:
        q = query.lower()
        findings = [f for f in findings if q in (f.get("title") or "").lower()]

    return {"findings": findings, "total": len(findings)}


async def get_finding(finding_id, client=None):
    """Fetch a single finding by ID."""
    data = await graphql(
        GET_FINDING_QUERY,
        variables={"id": finding_id},

    )
    return data.get("finding", {})


async def create_finding(title, description=None, severity=None, request_id=None, client=None):
    """Create a new finding attached to *request_id*.

    Caido's CreateFindingInput accepts: title, description, reporter.
    Severity is not a native Finding field; it is folded into the description.
    """
    if not request_id:
        raise ValueError("request_id is required to create a finding")

    input_fields = {"title": title, "reporter": "hermes-plugin"}
    if description:
        desc = description
        if severity:
            desc = f"**Severity:** {severity}\n\n{description}"
        input_fields["description"] = desc
    elif severity:
        input_fields["description"] = f"**Severity:** {severity}"

    data = await graphql(
        CREATE_FINDING_MUTATION,
        variables={"requestId": request_id, "input": input_fields},

    )
    result = data.get("createFinding", {})
    if result.get("error"):
        return {"error": result["error"]}
    return result.get("finding", {})


async def update_finding(finding_id, title=None, description=None, severity=None, state=None, client=None):
    """Update an existing finding."""
    input_fields = {}
    if title is not None:
        input_fields["title"] = title
    if description is not None:
        desc = description
        if severity:
            desc = f"**Severity:** {severity}\n\n{description}"
        input_fields["description"] = desc
    elif severity is not None:
        input_fields["description"] = f"**Severity:** {severity}"
    # state/hidden is handled via the hidden field if needed
    if state is not None:
        input_fields["hidden"] = state.lower() in ("hidden", "resolved", "false_positive")

    if not input_fields:
        return {"error": {"__typename": "ValidationError", "message": "No fields to update"}}

    data = await graphql(
        UPDATE_FINDING_MUTATION,
        variables={"id": finding_id, "input": input_fields},

    )
    result = data.get("updateFinding", {})
    if result.get("error"):
        return {"error": result["error"]}
    return result.get("finding", {})
