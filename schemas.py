"""Tool schemas for the Hermes Agent Caido plugin.

Each schema is a JSON Schema object that tells the LLM when and how to call
the corresponding tool.  All tools return JSON strings.
"""

CAIDO_SEARCH = {
    "name": "caido_search",
    "description": (
        "Search intercepted HTTP requests in the Caido proxy history using "
        "HTTPQL queries.  Use this to find requests matching specific criteria "
        "such as path substrings, methods, hosts, headers, status codes, etc.  "
        "Examples: 'req.path.cont:\"/api/\"', 'req.method = \"POST\"', "
        "'req.host = \"example.com\"', 'resp.status >= 400'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "HTTPQL query string, e.g. 'req.path.cont:\"/api/\"', "
                    "'req.method = \"POST\"', 'req.host = \"example.com\"'."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default 20).",
                "default": 20,
            },
            "compact": {
                "type": "boolean",
                "description": "Return compact one-line-per-entry format (default false).",
                "default": False,
            },
            "headers_only": {
                "type": "boolean",
                "description": "Return only the status line and headers, omitting the body (default false).",
                "default": False,
            },
        },
        "required": ["query"],
    },
}

CAIDO_RECENT = {
    "name": "caido_recent",
    "description": (
        "Get the most recent HTTP requests intercepted by the Caido proxy.  "
        "This is a shortcut for searching sorted by time descending.  Use when "
        "you want to see what traffic has been captured recently."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of recent requests to return (default 20).",
                "default": 20,
            },
            "compact": {
                "type": "boolean",
                "description": "Return compact one-line-per-entry format (default false).",
                "default": False,
            },
            "headers_only": {
                "type": "boolean",
                "description": "Return only the status line and headers, omitting the body (default false).",
                "default": False,
            },
        },
        "required": [],
    },
}

CAIDO_GET = {
    "name": "caido_get",
    "description": (
        "Retrieve a specific HTTP request and its response from the Caido proxy "
        "by request ID.  Use this to inspect a particular request/response pair "
        "in full detail, for example after finding it via caido_search."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "The unique request ID to retrieve.",
            },
            "raw": {
                "type": "boolean",
                "description": "Return the raw HTTP bytes instead of parsed format (default false).",
                "default": False,
            },
            "compact": {
                "type": "boolean",
                "description": "Return compact one-line-per-entry format (default false).",
                "default": False,
            },
            "headers_only": {
                "type": "boolean",
                "description": "Return only the status line and headers, omitting the body (default false).",
                "default": False,
            },
        },
        "required": ["request_id"],
    },
}

CAIDO_REPLAY_REQUEST = {
    "name": "caido_replay_request",
    "description": (
        "Replay an intercepted HTTP request through the Caido proxy.  Fetches "
        "the request by ID and re-sends it, preserving the original host, port, "
        "and TLS settings.  Use this to test mutations or verify vulnerabilities."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "The ID of the request to replay.",
            },
        },
        "required": ["request_id"],
    },
}

CAIDO_SEND_RAW = {
    "name": "caido_send_raw",
    "description": (
        "Send a raw, hand-crafted HTTP request through the Caido proxy.  Use "
        "this when you need to send a custom request that doesn't exist in the "
        "proxy history.  Provide the full raw HTTP request including the request "
        "line, headers, and body."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "raw_request": {
                "type": "string",
                "description": (
                    "Full raw HTTP request (request line + headers + body), e.g. "
                    "'GET /path HTTP/1.1\\r\\nHost: example.com\\r\\n\\r\\n'."
                ),
            },
            "host": {
                "type": "string",
                "description": "Target host (e.g. 'example.com').",
            },
            "tls": {
                "type": "boolean",
                "description": "Whether to use HTTPS (default true).",
                "default": True,
            },
            "port": {
                "type": "integer",
                "description": "Target port.  Defaults to 443 when TLS is true, 80 otherwise.",
            },
        },
        "required": ["raw_request", "host"],
    },
}

CAIDO_REPLAY_SESSIONS = {
    "name": "caido_replay_sessions",
    "description": (
        "List replay sessions in the current Caido project.  Use this to see "
        "available sessions before replaying requests or to review session state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of sessions to return (default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

CAIDO_CREATE_REPLAY_SESSION = {
    "name": "caido_create_replay_session",
    "description": (
        "Create a new replay session in Caido.  Use this before replaying "
        "requests that should be grouped under a named session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name for the new replay session.",
            },
            "collection_id": {
                "type": "string",
                "description": "Optional collection ID to place the session in.",
            },
        },
        "required": ["name"],
    },
}

CAIDO_RENAME_REPLAY_SESSION = {
    "name": "caido_rename_replay_session",
    "description": (
        "Rename an existing replay session.  Use this to give sessions "
        "descriptive names for organization."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "ID of the session to rename.",
            },
            "name": {
                "type": "string",
                "description": "New name for the session.",
            },
        },
        "required": ["session_id", "name"],
    },
}

CAIDO_DELETE_REPLAY_SESSIONS = {
    "name": "caido_delete_replay_sessions",
    "description": (
        "Delete one or more replay sessions by ID.  Use this to clean up "
        "sessions that are no longer needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of session IDs to delete.",
            },
        },
        "required": ["session_ids"],
    },
}

CAIDO_REPLAY_COLLECTIONS = {
    "name": "caido_replay_collections",
    "description": (
        "List replay collections in the current Caido project.  Use this to "
        "see what collections of replay requests are available."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of collections to return (default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

CAIDO_FINDINGS = {
    "name": "caido_findings",
    "description": (
        "List security findings recorded in the Caido project.  Use this to "
        "review discovered vulnerabilities and issues.  Optionally filter by "
        "title substring."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional filter — only return findings whose title contains this substring.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of findings to return (default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

CAIDO_GET_FINDING = {
    "name": "caido_get_finding",
    "description": (
        "Retrieve a specific security finding by ID.  Use this to get full "
        "details of a finding after listing with caido_findings."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "finding_id": {
                "type": "string",
                "description": "The ID of the finding to retrieve.",
            },
        },
        "required": ["finding_id"],
    },
}

CAIDO_CREATE_FINDING = {
    "name": "caido_create_finding",
    "description": (
        "Create a new security finding in the Caido project.  Use this to "
        "record a discovered vulnerability or issue with optional severity, "
        "description, and associated request ID."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the finding.",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the finding.",
            },
            "severity": {
                "type": "string",
                "description": "Severity level: critical, high, medium, low, or info.",
                "enum": ["critical", "high", "medium", "low", "info"],
            },
            "request_id": {
                "type": "string",
                "description": "Optional ID of the request associated with this finding.",
            },
        },
        "required": ["title"],
    },
}

CAIDO_UPDATE_FINDING = {
    "name": "caido_update_finding",
    "description": (
        "Update an existing security finding.  Use this to modify title, "
        "description, or severity of a finding."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "finding_id": {
                "type": "string",
                "description": "ID of the finding to update.",
            },
            "title": {
                "type": "string",
                "description": "New title for the finding.",
            },
            "description": {
                "type": "string",
                "description": "New description for the finding.",
            },
            "severity": {
                "type": "string",
                "description": "New severity level: critical, high, medium, low, or info.",
                "enum": ["critical", "high", "medium", "low", "info"],
            },
        },
        "required": ["finding_id"],
    },
}

CAIDO_EXPORT_CURL = {
    "name": "caido_export_curl",
    "description": (
        "Export an intercepted HTTP request as a curl command.  Use this to "
        "generate PoC commands for reports or manual testing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "The ID of the request to export as curl.",
            },
        },
        "required": ["request_id"],
    },
}

CAIDO_SCOPES = {
    "name": "caido_scopes",
    "description": (
        "List scopes defined in the current Caido project.  Scopes control "
        "which hosts and paths are included in or excluded from proxy "
        "interception and logging."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of scopes to return (default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

CAIDO_FILTERS = {
    "name": "caido_filters",
    "description": (
        "List filter presets configured in the Caido project.  Filter presets "
        "are saved HTTPQL-based filters that control what traffic is visible "
        "in the UI."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of filters to return (default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

CAIDO_ENVS = {
    "name": "caido_envs",
    "description": (
        "List environments configured in the Caido project.  Environments "
        "define target-specific settings such as hosts, ports, and TLS "
        "configurations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of environments to return (default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

CAIDO_PROJECTS = {
    "name": "caido_projects",
    "description": (
        "List all Caido projects.  Projects contain the full state of "
        "intercepted traffic, findings, and configuration."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of projects to return (default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

CAIDO_HEALTH = {
    "name": "caido_health",
    "description": (
        "Check the health and version of the connected Caido instance.  "
        "Use this to verify connectivity and confirm the Caido version."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
