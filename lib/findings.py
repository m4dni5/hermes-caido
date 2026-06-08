"""Findings management via raw GraphQL."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from client import graphql


async def list_findings(query=None, limit=50, client=None):
    """List findings with optional text filter."""
    gql = """
    query Findings($input: FindingsInput!) {
      findings(input: $input) {
        edges {
          node {
            id
            title
            description
            severity
            state
            createdAt
            request { id host method path }
          }
        }
        totalCount
      }
    }
    """
    variables = {"input": {"limit": limit, "offset": 0}}
    result = await graphql(gql, variables, client=client)
    if "error" in result:
        return result
    findings_data = result.get("data", {}).get("findings", {})
    findings = [
        edge["node"] for edge in findings_data.get("edges", [])
    ]
    # Client-side text filter if query provided
    if query:
        q = query.lower()
        findings = [f for f in findings if q in f.get("title", "").lower()
                    or q in (f.get("description") or "").lower()]
    return {"findings": findings, "total": findings_data.get("totalCount", 0)}


async def get_finding(finding_id, client=None):
    """Get a single finding by ID."""
    gql = """
    query GetFinding($id: ID!) {
      finding(id: $id) {
        id
        title
        description
        severity
        state
        createdAt
        request { id host method path }
      }
    }
    """
    result = await graphql(gql, {"id": finding_id}, client=client)
    if "error" in result:
        return result
    return result.get("data", {}).get("finding", {"error": "Finding not found"})


async def create_finding(title, description=None, severity=None, request_id=None, client=None):
    """Create a new finding."""
    gql = """
    mutation CreateFinding($input: CreateFindingInput!) {
      createFinding(input: $input) {
        ... on CreateFindingSuccess {
          finding { id title }
        }
        ... on CreateFindingError {
          message
        }
      }
    }
    """
    inp = {"title": title}
    if description:
        inp["description"] = description
    if severity:
        inp["severity"] = severity
    if request_id:
        inp["requestId"] = request_id
    result = await graphql(gql, {"input": inp}, client=client)
    if "error" in result:
        return result
    payload = result.get("data", {}).get("createFinding", {})
    if "message" in payload:
        return {"error": payload["message"]}
    return payload.get("finding", {"error": "Unexpected response"})


async def update_finding(finding_id, title=None, description=None, severity=None, state=None, client=None):
    """Update an existing finding."""
    gql = """
    mutation UpdateFinding($input: UpdateFindingInput!) {
      updateFinding(input: $input) {
        ... on UpdateFindingSuccess {
          finding { id title }
        }
        ... on UpdateFindingError {
          message
        }
      }
    }
    """
    inp = {"id": finding_id}
    if title is not None:
        inp["title"] = title
    if description is not None:
        inp["description"] = description
    if severity is not None:
        inp["severity"] = severity
    if state is not None:
        inp["state"] = state
    result = await graphql(gql, {"input": inp}, client=client)
    if "error" in result:
        return result
    payload = result.get("data", {}).get("updateFinding", {})
    if "message" in payload:
        return {"error": payload["message"]}
    return payload.get("finding", {"error": "Unexpected response"})
