"""Tool schemas for the Hermes Agent Caido plugin.

Each schema is a JSON Schema object that tells the LLM when and how to call
the corresponding tool.  All tools return JSON strings.

Registered tools (7):
  caido_onboard, caido_search, caido_recent, caido_get,
  caido_findings, caido_create_finding, caido_health

All other operations live in bundled skills:
  caido:replay  — session management, edit-and-replay
  caido:utils   — auth setup, findings CRUD, export curl, scopes, filters, envs, projects
  caido:automate — sessions, placeholders, payloads, task control
"""

CAIDO_ONBOARD = {
    "name": "caido_onboard",
    "description": (
        "Connect to Caido and gather full context in one call. Returns health, "
        "auth status, active project, scopes, intercept config, recent traffic "
        "summary, findings count, and available hosted files. Use this at the "
        "start of any Caido session to orient yourself. "
        "If auth fails, load the caido:utils skill and run auth.setup(). "
        "Local instances (127.0.0.1:8080) connect as guest — no PAT needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

CAIDO_SEARCH = {
    "name": "caido_search",
    "description": (
        "Search the Caido **proxy history** — the log of all HTTP traffic that "
        "passed through the proxy — using HTTPQL queries.  Use this to find "
        "requests matching specific criteria such as path substrings, methods, "
        "hosts, headers, status codes, etc.  "
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
        "Get the most recent HTTP requests from the Caido **proxy history**.  "
        "This is a shortcut for searching sorted by time descending.  Use when "
        "you want to see what traffic the proxy has captured recently."
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
        "Retrieve a specific HTTP request and its response from the Caido "
        "**proxy history** — the log of all traffic that passed through the proxy.  "
        "Use this to inspect a request/response pair after finding it via "
        "caido_search or caido_recent.  For replay requests, use the replay skill.  "
        "For automate (fuzzer) requests, use the automate skill."
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

CAIDO_HEALTH = {
    "name": "caido_health",
    "description": (
        "Check the health and version of the connected Caido instance.  "
        "Use this to verify connectivity and confirm the Caido version. "
        "If the check fails, load the caido:utils skill and run auth.setup()."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
