"""Exercise the real image's persistent account setup. Requires Docker."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid


IMAGE = os.environ.get("COOKCLI_TEST_IMAGE", "ha-cookcli:ci")


def docker(*args, **kwargs):
    return subprocess.run(
        ["docker", *args], check=True, text=True, capture_output=True, **kwargs
    ).stdout


class StartupTest(unittest.TestCase):
    def test_persistent_users(self):
        with tempfile.TemporaryDirectory(prefix="cookcli-test-") as directory:
            data = Path(directory)
            options = data / "options.json"
            mount = f"type=bind,src={data.resolve()},dst=/data"

            # A similar existing username must not prevent creating 'jp'.
            (data / "cookcli").mkdir()
            docker(
                "run", "--rm", "-i", "--mount", mount,
                "--env", "COOK_CONFIG_DIR=/data/cookcli",
                "--entrypoint", "cook", IMAGE,
                "server", "user", "add", "jpsuffix",
                input="ci-only-existing-password\n",
            )

            def configure(password):
                options.write_text(json.dumps({
                    "users": [{"username": "jp", "password": password}],
                    "cors_origin": "http://homeassistant.local:9080",
                }), encoding="utf-8")

            def start_and_stop():
                name = "cookcli-test-" + uuid.uuid4().hex
                docker("run", "--detach", "--name", name, "--mount", mount, IMAGE)
                try:
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        # CookCLI can log server startup to stderr.
                        result = subprocess.run(
                            ["docker", "logs", name], check=True,
                            text=True, capture_output=True,
                        )
                        logs = result.stdout + result.stderr
                        if "Listening on" in logs:
                            listing = docker(
                                "exec", "--env", "COOK_CONFIG_DIR=/data/cookcli",
                                name, "cook", "server", "user", "list",
                            )
                            self.assertEqual(
                                {line.split()[0] for line in listing.splitlines() if line.strip()},
                                {"jp", "jpsuffix"},
                            )
                            return logs
                        if docker("inspect", "--format", "{{.State.Running}}", name).strip() != "true":
                            self.fail(f"Container exited before serving:\n{logs}")
                        time.sleep(0.2)
                    self.fail(f"Server did not start in 30 seconds:\n{logs}")
                finally:
                    docker("rm", "--force", name)

            configure("ci-only-first-password")
            self.assertIn("CookCLI: user added: jp\n", start_and_stop())

            restart_logs = start_and_stop()
            self.assertNotIn("CookCLI: user added:", restart_logs)
            self.assertNotIn("CookCLI: password updated:", restart_logs)

            configure("ci-only-changed-password")
            self.assertIn("CookCLI: password updated: jp\n", start_and_stop())


if __name__ == "__main__":
    unittest.main()
