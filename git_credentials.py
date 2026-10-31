"""Non-persistent Git credential helper, scoped to one HTTPS repository."""

import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


def response(request, credentials):
    url = urlsplit(credentials["repository"])
    expected_host = url.netloc.lower()
    expected_path = url.path.strip("/")
    if (request.get("protocol") != "https"
            or request.get("host", "").lower() != expected_host
            or request.get("path", "").strip("/") != expected_path
            or request.get("username", credentials["username"]) != credentials["username"]):
        return ""
    return f"username={credentials['username']}\npassword={credentials['token']}\n\n"


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "get":
        return
    try:
        request = dict(line.rstrip("\n").split("=", 1) for line in sys.stdin if "=" in line)
        credentials = json.loads(Path(os.environ["COOKCLI_GIT_CREDENTIALS"]).read_text(encoding="utf-8"))
        sys.stdout.write(response(request, credentials))
    except (OSError, ValueError, KeyError):
        # Never include credential data in exception output or logs.
        return


if __name__ == "__main__":
    main()
