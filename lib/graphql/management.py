"""
Caido management operations via raw GraphQL.
Uses the real Caido GraphQL schema (error unions with __typename).
"""

import sys
from pathlib import Path

from .client import graphql


# ─── Scopes ──────────────────────────────────────────────────────────────────

SCOPES_QUERY = """query Scopes { scopes { id name } }"""

GET_SCOPE_QUERY = """query Scope($id: ID!) { scope(id: $id) { id name allow deny } }"""

CREATE_SCOPE_MUTATION = """mutation CreateScope($input: CreateScopeInput!) {
  createScope(input: $input) {
    error { __typename ... on NameTakenUserError { message } ... on PermissionDeniedUserError { message } ... on OtherUserError { message } }
    scope { id name }
  }
}"""

DELETE_SCOPE_MUTATION = """mutation DeleteScope($id: ID!) {
  deleteScope(id: $id) {
    deletedId
  }
}"""


# ─── Filters ─────────────────────────────────────────────────────────────────

FILTERS_QUERY = """query FilterPresets { filterPresets { id name alias clause { __typename ... on HTTPQL { code } } } }"""

CREATE_FILTER_MUTATION = """mutation CreateFilterPreset($input: CreateFilterPresetInput!) {
  createFilterPreset(input: $input) {
    error { __typename ... on NameTakenUserError { message } ... on AliasTakenUserError { message } ... on PermissionDeniedUserError { message } ... on OtherUserError { message } }
    filter { id name }
  }
}"""

DELETE_FILTER_MUTATION = """mutation DeleteFilterPreset($id: ID!) {
  deleteFilterPreset(id: $id) { deletedId }
}"""


# ─── Environments ────────────────────────────────────────────────────────────

ENVIRONMENTS_QUERY = """fragment EnvironmentFull on Environment { id name variables { name value kind } version }
query Environments { environments { ...EnvironmentFull } }"""

CREATE_ENVIRONMENT_MUTATION = """mutation CreateEnvironment($input: CreateEnvironmentInput!) {
  createEnvironment(input: $input) {
    error { __typename ... on NameTakenUserError { message } ... on PermissionDeniedUserError { message } ... on OtherUserError { message } }
    environment { id name variables { name value kind } version }
  }
}"""

DELETE_ENVIRONMENT_MUTATION = """mutation DeleteEnvironment($id: ID!) {
  deleteEnvironment(id: $id) {
    deletedId
    error { __typename ... on UnknownIdUserError { message } ... on OtherUserError { message } }
  }
}"""


# ─── Projects ────────────────────────────────────────────────────────────────

PROJECTS_QUERY = """fragment ProjectFull on Project { id name path status temporary createdAt updatedAt version size readOnly }
query Projects { projects { ...ProjectFull } }"""

CREATE_PROJECT_MUTATION = """mutation CreateProject($input: CreateProjectInput!) {
  createProject(input: $input) {
    error { __typename ... on NameTakenUserError { message } ... on PermissionDeniedUserError { message } ... on OtherUserError { message } }
    project { id name path status temporary createdAt updatedAt version size readOnly }
  }
}"""

DELETE_PROJECT_MUTATION = """mutation DeleteProject($id: ID!) {
  deleteProject(id: $id) {
    deletedId
    error { __typename ... on ProjectUserError { message } ... on UnknownIdUserError { message } ... on OtherUserError { message } }
  }
}"""


# ─── Tasks ───────────────────────────────────────────────────────────────────

TASKS_QUERY = """fragment TaskMeta on Task { __typename id createdAt }
fragment ReplayTaskMeta on ReplayTask { ...TaskMeta replayEntry { id } }
query Tasks { tasks { ...TaskMeta ... on ReplayTask { ...ReplayTaskMeta } } }"""

CANCEL_TASK_MUTATION = """mutation cancelTask($id: ID!) {
  cancelTask(id: $id) {
    cancelledId
    error { __typename ... on UnknownIdUserError { message } ... on OtherUserError { message } }
  }
}"""


# ─── Hosted Files ────────────────────────────────────────────────────────────

HOSTED_FILES_QUERY = """query HostedFiles { hostedFiles { id name path size status createdAt updatedAt } }"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _check_error(result: dict) -> str | None:
    """Return error message string if the mutation result has an error, else None."""
    err = result.get("error")
    if err:
        typename = err.get("__typename", "")
        msg = err.get("message", "")
        return f"{typename}: {msg}" if typename and msg else (msg or typename or "Unknown error")
    return None


def _extract_deleted(result: dict, id_key: str = "deletedId") -> dict:
    """For delete/cancel mutations: check error, return {id: ...} on success."""
    err_msg = _check_error(result)
    if err_msg:
        return {"error": err_msg}
    deleted_id = result.get(id_key)
    if deleted_id is None:
        return {"error": "No ID returned from delete operation"}
    return {"id": deleted_id}


# ─── Scopes ──────────────────────────────────────────────────────────────────

async def scopes(limit=50, client=None) -> list:
    try:
        result = await graphql(SCOPES_QUERY)
        return result.get("scopes", [])
    except Exception as e:
        return {"error": str(e)}


async def get_scope(scope_id, client=None) -> dict:
    try:
        result = await graphql(GET_SCOPE_QUERY, {"id": scope_id})
        scope = result.get("scope")
        if scope is None:
            return {"error": "Scope not found"}
        return scope
    except Exception as e:
        return {"error": str(e)}


async def create_scope(name, allow=None, deny=None, client=None) -> dict:
    try:
        input_vars = {"name": name, "allowlist": allow or [], "denylist": deny or []}
        result = await graphql(CREATE_SCOPE_MUTATION, {"input": input_vars})
        payload = result.get("createScope", {})
        err_msg = _check_error(payload)
        if err_msg:
            return {"error": err_msg}
        return payload.get("scope", {"error": "No scope returned"})
    except Exception as e:
        return {"error": str(e)}


async def delete_scope(scope_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_SCOPE_MUTATION, {"id": scope_id})
        return _extract_deleted(result.get("deleteScope", {}))
    except Exception as e:
        return {"error": str(e)}


# ─── Filters ─────────────────────────────────────────────────────────────────

async def filters(limit=50, client=None) -> list:
    try:
        result = await graphql(FILTERS_QUERY)
        return result.get("filterPresets", [])
    except Exception as e:
        return {"error": str(e)}


async def create_filter(name, httpql, client=None) -> dict:
    try:
        result = await graphql(CREATE_FILTER_MUTATION, {"input": {"name": name, "alias": name.lower().replace(" ", "-"), "clause": {"HTTPQL": {"code": httpql}}, "global": False}})
        payload = result.get("createFilterPreset", {})
        err_msg = _check_error(payload)
        if err_msg:
            return {"error": err_msg}
        return payload.get("filter", {"error": "No filter returned"})
    except Exception as e:
        return {"error": str(e)}


async def delete_filter(filter_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_FILTER_MUTATION, {"id": filter_id})
        return _extract_deleted(result.get("deleteFilterPreset", {}))
    except Exception as e:
        return {"error": str(e)}


# ─── Environments ────────────────────────────────────────────────────────────

async def environments(limit=50, client=None) -> list:
    try:
        result = await graphql(ENVIRONMENTS_QUERY)
        return result.get("environments", [])
    except Exception as e:
        return {"error": str(e)}


async def create_environment(name, variables=None, client=None) -> dict:
    try:
        input_vars = {"name": name}
        if variables is not None:
            input_vars["variables"] = variables
        result = await graphql(CREATE_ENVIRONMENT_MUTATION, {"input": input_vars})
        payload = result.get("createEnvironment", {})
        err_msg = _check_error(payload)
        if err_msg:
            return {"error": err_msg}
        return payload.get("environment", {"error": "No environment returned"})
    except Exception as e:
        return {"error": str(e)}


async def delete_environment(env_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_ENVIRONMENT_MUTATION, {"id": env_id})
        return _extract_deleted(result.get("deleteEnvironment", {}))
    except Exception as e:
        return {"error": str(e)}


# ─── Projects ────────────────────────────────────────────────────────────────

async def projects(limit=50, client=None) -> list:
    try:
        result = await graphql(PROJECTS_QUERY)
        return result.get("projects", [])
    except Exception as e:
        return {"error": str(e)}


async def create_project(name, temporary=False, client=None) -> dict:
    try:
        result = await graphql(CREATE_PROJECT_MUTATION, {"input": {"name": name, "temporary": temporary}})
        payload = result.get("createProject", {})
        err_msg = _check_error(payload)
        if err_msg:
            return {"error": err_msg}
        return payload.get("project", {"error": "No project returned"})
    except Exception as e:
        return {"error": str(e)}


async def delete_project(project_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_PROJECT_MUTATION, {"id": project_id})
        return _extract_deleted(result.get("deleteProject", {}))
    except Exception as e:
        return {"error": str(e)}


# ─── Hosted Files ────────────────────────────────────────────────────────────

async def hosted_files(limit=50, client=None) -> list:
    try:
        result = await graphql(HOSTED_FILES_QUERY)
        return result.get("hostedFiles", [])
    except Exception as e:
        return {"error": str(e)}


# ─── Tasks ───────────────────────────────────────────────────────────────────

async def tasks(limit=50, client=None) -> list:
    try:
        result = await graphql(TASKS_QUERY)
        return result.get("tasks", [])
    except Exception as e:
        return {"error": str(e)}


async def cancel_task(task_id, client=None) -> dict:
    try:
        result = await graphql(CANCEL_TASK_MUTATION, {"id": task_id})
        return _extract_deleted(result.get("cancelTask", {}), id_key="cancelledId")
    except Exception as e:
        return {"error": str(e)}
