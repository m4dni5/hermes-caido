"""Caido management operations — sync wrappers.

Usage:
    import management
    scopes = management.scopes()
    management.create_scope(name="Target", allow=["*.target.com"])
"""

from __future__ import annotations
from sync import sync_run
from graphql.management import (
    scopes as _scopes,
    get_scope as _get_scope,
    create_scope as _create_scope,
    delete_scope as _delete_scope,
    rename_scope as _rename_scope,
    update_scope as _update_scope,
    filters as _filters,
    create_filter as _create_filter,
    delete_filter as _delete_filter,
    environments as _environments,
    create_environment as _create_environment,
    delete_environment as _delete_environment,
    projects as _projects,
    create_project as _create_project,
    delete_project as _delete_project,
    hosted_files as _hosted_files,
    tasks as _tasks,
    cancel_task as _cancel_task,
)


def scopes(limit: int = 50) -> list:
    return sync_run(_scopes, limit)


def get_scope(scope_id: str) -> dict:
    return sync_run(_get_scope, scope_id)


def create_scope(name: str, allow: list[str] | None = None, deny: list[str] | None = None) -> dict:
    return sync_run(_create_scope, name=name, allow=allow, deny=deny)


def delete_scope(scope_id: str) -> dict:
    return sync_run(_delete_scope, scope_id)


def rename_scope(scope_id: str, name: str) -> dict:
    return sync_run(_rename_scope, scope_id, name)


def update_scope(scope_id: str, name: str | None = None, allowlist: list[str] | None = None, denylist: list[str] | None = None) -> dict:
    return sync_run(_update_scope, scope_id, name=name, allowlist=allowlist, denylist=denylist)


def filters(limit: int = 50) -> list:
    return sync_run(_filters, limit)


def create_filter(name: str, httpql: str) -> dict:
    return sync_run(_create_filter, name=name, httpql=httpql)


def delete_filter(filter_id: str) -> dict:
    return sync_run(_delete_filter, filter_id)


def environments(limit: int = 50) -> list:
    return sync_run(_environments, limit)


def create_environment(name: str, variables: list[dict] | None = None) -> dict:
    return sync_run(_create_environment, name=name, variables=variables)


def delete_environment(env_id: str) -> dict:
    return sync_run(_delete_environment, env_id)


def projects(limit: int = 50) -> list:
    return sync_run(_projects, limit)


def create_project(name: str, temporary: bool = False) -> dict:
    return sync_run(_create_project, name=name, temporary=temporary)


def delete_project(project_id: str) -> dict:
    return sync_run(_delete_project, project_id)


def hosted_files(limit: int = 50) -> list:
    return sync_run(_hosted_files, limit)


def tasks(limit: int = 50) -> list:
    return sync_run(_tasks, limit)


def cancel_task(task_id: str) -> dict:
    return sync_run(_cancel_task, task_id)
