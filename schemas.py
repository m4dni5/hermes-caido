"""Tool schemas for the Hermes Agent Caido plugin.

Each schema is a JSON Schema object that tells the LLM when and how to call
the corresponding tool.  All tools return JSON strings.

Registered tools (12):
  caido_onboard, caido_search, caido_recent, caido_get,
  caido_findings, caido_create_finding, caido_health,
  caido_auth_setup, caido_export_curl, caido_replay,
  caido_automate, caido_automate_status

The caido:automate skill is the recipe cookbook for automate workflows
(strategy/payload decisions, pitfalls, IDOR patterns).
"""

CAIDO_ONBOARD = {
    "name": "caido_onboard",
    "description": (
        "Connect to Caido and gather full context in one call. Returns health, "
        "auth status, active project, scopes, intercept config, recent traffic "
        "summary, findings count, and available hosted files. Use this at the "
        "start of any Caido session to orient yourself. "
        "If auth fails, run caido_auth_setup."
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
        "passed through the proxy — using HTTPQL queries. Use this to find "
        "requests matching specific criteria such as path substrings, methods, "
        "hosts, headers, or status codes. HTTPQL string values are quoted, "
        "integers are not; negations use ne/ncont/nlike/nregex."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "HTTPQL query string over req/resp fields.",
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
        "**proxy history** — the log of all traffic that passed through the proxy. "
        "Accepts **both ID formats**: the GraphQL request id returned by "
        "caido_search/caido_recent, AND the number shown in the Caido UI history "
        "table (the UI number is the request's metadata id — caido_get resolves "
        "it automatically). Use this to inspect a request/response pair after "
        "finding it via caido_search or caido_recent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "Request ID to retrieve — either the id from caido_search/caido_recent output, or the number shown in the Caido UI history table.",
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
        "Create a new security finding in the Caido project, attached to a "
        "specific request. Use this to record a discovered vulnerability or "
        "issue with optional severity and description."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the finding.",
            },
            "request_id": {
                "type": "string",
                "description": "ID of the request this finding is attached to — either from caido_search/caido_recent output, or the number shown in the Caido UI history table.",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the finding.",
            },
            "severity": {
                "type": "string",
                "description": "Severity level: critical, high, medium, low, or info (folded into the description).",
                "enum": ["critical", "high", "medium", "low", "info"],
            },
        },
        "required": ["title", "request_id"],
    },
}

CAIDO_HEALTH = {
    "name": "caido_health",
    "description": (
        "Check the health and version of the connected Caido instance.  "
        "Use this to verify connectivity and confirm the Caido version. "
        "If the check fails, run caido_auth_setup."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

CAIDO_AUTH_SETUP = {
    "name": "caido_auth_setup",
    "description": (
        "Run the Caido OAuth2 device-code auth flow in an isolated subprocess. "
        "Configures credentials and caches the access token. Use when "
        "caido_onboard or caido_health reports an auth error, or after a token "
        "expiry. Requires a PAT (CAIDO_PAT) and instance URL (CAIDO_URL) — "
        "pass them explicitly or ensure they are set in the environment."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pat": {
                "type": "string",
                "description": "Caido Personal Access Token. Falls back to CAIDO_PAT env var or the Hermes .env file.",
            },
            "url": {
                "type": "string",
                "description": "Caido instance URL. Falls back to CAIDO_URL env var or the Hermes .env file.",
            },
        },
        "required": [],
    },
}

CAIDO_EXPORT_CURL = {
    "name": "caido_export_curl",
    "description": (
        "Export a request from proxy history as a curl command. "
        "Use to hand a request to the user, feed it into ffuf or another "
        "terminal tool, or reproduce it outside Caido. Accepts both the "
        "caido_search/caido_recent request id and the number shown in the Caido "
        "UI history table."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "Request ID — either from caido_search/caido_recent output, or the number shown in the Caido UI history table.",
            },
        },
        "required": ["request_id"],
    },
}

CAIDO_REPLAY = {
    "name": "caido_replay",
    "description": (
        "Replay an HTTP request from proxy history, optionally with edits. "
        "Sends the request as-is, or apply edits (method/path/headers/body) "
        "before sending — useful for testing modified requests, auth bypasses, "
        "or parameter changes. Accepts both the caido_search/caido_recent "
        "request id and the number shown in the Caido UI history table. "
        "Use when the traffic should be visible in Caido (shared workspace). "
        "For quick private probes the user doesn't need to see, plain curl is "
        "faster."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "Request ID to replay — either from caido_search/caido_recent output, or the number shown in the Caido UI history table.",
            },
            "path": {
                "type": "string",
                "description": "Optional new path, e.g. /api/admin/users.",
            },
            "method": {
                "type": "string",
                "description": "Optional new HTTP method, e.g. POST.",
            },
            "headers": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "description": "Optional headers to set or replace, as [name, value] pairs, e.g. [[\"X-Forwarded-For\", \"127.0.0.1\"]].",
            },
            "body": {
                "type": "string",
                "description": "Optional new request body (Content-Length updated automatically).",
            },
            "session_name": {
                "type": "string",
                "description": "Optional name for the replay session.",
            },
        },
        "required": ["request_id"],
    },
}

CAIDO_AUTOMATE = {
    "name": "caido_automate",
    "description": (
        "Run a Caido Automate campaign in one call. Takes a source "
        "request, a target value to automate, a payload list, and a strategy; "
        "creates the session, embeds the FUZZ placeholder, configures payloads, "
        "and starts the task. Returns {session_id, task_id}. Use for parameter "
        "automate, IDOR discovery, auth bypass attempts, and similar — when the "
        "run should be visible in Caido (shared workspace). For high-volume or "
        "headless fuzzing, ffuf is often the better tool: export the request "
        "with caido_export_curl and run ffuf directly. For strategy/payload "
        "guidance see the caido:automate skill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "description": "Source request ID — either from caido_search/caido_recent output, or the number shown in the Caido UI history table.",
            },
            "target": {
                "type": "string",
                "description": "Value in the request to replace with the FUZZ placeholder, e.g. 'id=42' or 'admin'. This is the position payloads get injected.",
            },
            "payloads": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Payload values to inject, e.g. ['1', '2', '3', 'admin'].",
            },
            "strategy": {
                "type": "string",
                "enum": ["ALL", "SEQUENTIAL", "MATRIX", "PARALLEL"],
                "default": "ALL",
                "description": "How payloads combine: ALL replaces every placeholder at once; SEQUENTIAL replaces one at a time; MATRIX/PARALLEL need one payload set per placeholder (see skill).",
            },
            "session_name": {
                "type": "string",
                "description": "Optional name for the automate session.",
            },
        },
        "required": ["request_id", "target", "payloads"],
    },
}

CAIDO_AUTOMATE_STATUS = {
    "name": "caido_automate_status",
    "description": (
        "Check the status of a Caido Automate task. Returns the task id, paused "
        "state, and the automate entry it runs. Use after caido_automate to poll "
        "completion. Result bodies are not yet returned (see skill)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID returned by caido_automate.",
            },
        },
        "required": ["task_id"],
    },
}
