#!/usr/bin/env python3
"""Generate a test JWT token from the local mock-oauth2-server."""

import argparse
import json
import sys
import urllib.parse
import urllib.request


def main() -> None:
    """Execute the token generation script."""
    parser = argparse.ArgumentParser(description="Generate a mock OAuth token.")
    parser.add_argument("--sub", default="quoin-api", help="Subject (NUID)")
    parser.add_argument(
        "--roles", default="users.read", help="Comma-separated roles"
    )
    args = parser.parse_args()

    # The mock-oauth2-server injects the 'scope' parameter directly into the
    # 'aud' array claim. By appending 'default', we pass audience validation,
    # and by changing the local .env to read roles from 'aud', we get roles.
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": args.sub,
            "client_secret": "secret",
            "scope": f"default {args.roles.replace(',', ' ')}",
        }
    ).encode()

    try:
        req = urllib.request.Request(
            "http://localhost:8080/default/token", data=data
        )
        response = urllib.request.urlopen(req)
        token = json.loads(response.read())["access_token"]
        print(token)
    except Exception as e:
        print(f"Error fetching token: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
