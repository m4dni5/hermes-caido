"""
Caido management operations via raw GraphQL.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from client import graphql


SCOPES_QUERY = """query Scopes { scopes { id name } }"""

GET_SCOPE_QUERY = """query GetScope($id: ID!) { scope(id: $id) { id name allow deny } }"""

CREATE_SCOPE_MUTATION = """mutation CreateScope($input: CreateScopeInput!) {
  createScope(input: $input) {
    ... on CreateScopeSuccess { scope { id name } }
    ... on CreateScopeError { message }
  }
}"""

DELETE_SCOPE_MUTATION = """mutation DeleteScope($id: ID!) {
  deleteScope(id: $id) {
    ... on DeleteScopeSuccess { id }
    ... on DeleteScopeError { message }
  }
}"""

FILTERS_QUERY = """query Filters { filters { id name alias clause kind } }"""

CREATE_FILTER_MUTATION = """mutation CreateFilter($input: CreateFilterInput!) {
  createFilter(input: $input) {
    ... on CreateFilterSuccess { filter { id name } }
    ... on CreateFilterError { message }
  }
}"""

DELETE_FILTER_MUTATION = """mutation DeleteFilter($id: ID!) {
  deleteFilter(id: $id) {
    ... on DeleteFilterSuccess { id }
    ... on DeleteFilterError { message }
  }
}"""

ENVIRONMENTS_QUERY = """query Environments { environments { id name version variables { key value } } }"""

CREATE_ENVIRONMENT_MUTATION = """mutation CreateEnvironment($input: CreateEnvironmentInput!) {
  createEnvironment(input: $input) {
    ... on CreateEnvironmentSuccess { environment { id name } }
    ... on CreateEnvironmentError { message }
  }
}"""

DELETE_ENVIRONMENT_MUTATION = """mutation DeleteEnvironment($id: ID!) {
  deleteEnvironment(id: $id) {
    ... on DeleteEnvironmentSuccess { id }
    ... on DeleteEnvironmentError { message }
  }
}"""

PROJECTS_QUERY = """query Projects { projects { id name temporary createdAt updatedAt version size readOnly status } }"""

CREATE_PROJECT_MUTATION = """mutation CreateProject($input: CreateProjectInput!) {
  createProject(input: $input) {
    ... on CreateProjectSuccess { project { id name } }
    ... on CreateProjectError { message }
  }
}"""

DELETE_PROJECT_MUTATION = """mutation DeleteProject($id: ID!) {
  deleteProject(id: $id) {
    ... on DeleteProjectSuccess { id }
    ... on DeleteProjectError { message }
  }
}"""

HOSTED_FILES_QUERY = """query HostedFiles { hostedFiles { id name url size } }"""

TASKS_QUERY = """query Tasks { tasks { id status type createdAt } }"""

CANCEL_TASK_MUTATION = """mutation CancelTask($id: ID!) {
  cancelTask(id: $id) {
    ... on CancelTaskSuccess { id }
    ... on CancelTaskError { message }
  }
}"""


def _handle_union(data: dict, success_key: str) -> dict:
    """Extract result from a union type response. Returns error dict if it's an error variant."""
    if not data:
        return {"error": "Empty response"}
    if "message" in data:
        return {"error": data["message"]}
    return data


async def scopes(limit=50, client=None) -> list:
    try:
        result = await graphql(SCOPES_QUERY, client=client)
        return result.get("scopes", [])
    except Exception as e:
        return {"error": str(e)}


async def get_scope(scope_id, client=None) -> dict:
    try:
        result = await graphql(GET_SCOPE_QUERY, {"id": scope_id}, client=client)
        scope = result.get("scope")
        if scope is None:
            return {"error": "Scope not found"}
        return scope
    except Exception as e:
        return {"error": str(e)}


async def create_scope(name, allow=None, deny=None, client=None) -> dict:
    try:
        input_vars = {"name": name}
        if allow is not None:
            input_vars["allow"] = allow
        if deny is not None:
            input_vars["deny"] = deny
        result = await graphql(CREATE_SCOPE_MUTATION, {"input": input_vars}, client=client)
        return _handle_union(result.get("createScope"), "scope")
    except Exception as e:
        return {"error": str(e)}


async def delete_scope(scope_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_SCOPE_MUTATION, {"id": scope_id}, client=client)
        return _handle_union(result.get("deleteScope"), "id")
    except Exception as e:
        return {"error": str(e)}


async def filters(limit=50, client=None) -> list:
    try:
        result = await graphql(FILTERS_QUERY, client=client)
        return result.get("filters", [])
    except Exception as e:
        return {"error": str(e)}


async def create_filter(name, httpql, client=None) -> dict:
    try:
        result = await graphql(CREATE_FILTER_MUTATION, {"input": {"name": name, "httpql": httpql}}, client=client)
        return _handle_union(result.get("createFilter"), "filter")
    except Exception as e:
        return {"error": str(e)}


async def delete_filter(filter_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_FILTER_MUTATION, {"id": filter_id}, client=client)
        return _handle_union(result.get("deleteFilter"), "id")
    except Exception as e:
        return {"error": str(e)}


async def environments(limit=50, client=None) -> list:
    try:
        result = await graphql(ENVIRONMENTS_QUERY, client=client)
        return result.get("environments", [])
    except Exception as e:
        return {"error": str(e)}


async def create_environment(name, variables=None, client=None) -> dict:
    try:
        input_vars = {"name": name}
        if variables is not None:
            input_vars["variables"] = variables
        result = await graphql(CREATE_ENVIRONMENT_MUTATION, {"input": input_vars}, client=client)
        return _handle_union(result.get("createEnvironment"), "environment")
    except Exception as e:
        return {"error": str(e)}


async def delete_environment(env_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_ENVIRONMENT_MUTATION, {"id": env_id}, client=client)
        return _handle_union(result.get("deleteEnvironment"), "id")
    except Exception as e:
        return {"error": str(e)}


async def projects(limit=50, client=None) -> list:
    try:
        result = await graphql(PROJECTS_QUERY, client=client)
        return result.get("projects", [])
    except Exception as e:
        return {"error": str(e)}


async def create_project(name, client=None) -> dict:
    try:
        result = await graphql(CREATE_PROJECT_MUTATION, {"input": {"name": name, "temporary": False}}, client=client)
        return _handle_union(result.get("createProject"), "project")
    except Exception as e:
        return {"error": str(e)}


async def delete_project(project_id, client=None) -> dict:
    try:
        result = await graphql(DELETE_PROJECT_MUTATION, {"id": project_id}, client=client)
        return _handle_union(result.get("deleteProject"), "id")
    except Exception as e:
        return {"error": str(e)}


async def hosted_files(limit=50, client=None) -> list:
    try:
        result = await graphql(HOSTED_FILES_QUERY, client=client)
        return result.get("hostedFiles", [])
    except Exception as e:
        return {"error": str(e)}


async def tasks(limit=50, client=None) -> list:
    try:
        result = await graphql(TASKS_QUERY, client=client)
        return result.get("tasks", [])
    except Exception as e:
        return {"error": str(e)}


async def cancel_task(task_id, client=None) -> dict:
    try:
        result = await graphql(CANCEL_TASK_MUTATION, {"id": task_id}, client=client)
        return _handle_union(result.get("cancelTask"), "id")
    except Exception as e:
        return {"error": str(e)}
