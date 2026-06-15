#!/usr/bin/env python3
"""Standalone auth helper for Caido plugin.

Runs the OAuth2 device code flow in an isolated process — avoids event loop
and aiohttp state conflicts when called from within the Hermes agent's
async context.

Usage:
    python3 auth_helper.py <pat> <url>

Writes token to ~/.hermes/cache/caido-token.json on success.
Outputs JSON result to stdout.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from graphql.client import _do_device_flow, _save_cached_token, _access_token, _refresh_token, _expires_at


async def main(pat: str, url: str) -> dict:
    try:
        await _do_device_flow(url, pat)
        return {
            "status": "success",
            "token_cached": True,
            "expires_at": _expires_at.isoformat() if _expires_at else None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: auth_helper.py <pat> <url>"}))
        sys.exit(1)

    pat = sys.argv[1]
    url = sys.argv[2]
    result = asyncio.run(main(pat, url))
    print(json.dumps(result))
    sys.exit(0 if result.get("status") == "success" else 1)
