"""End-to-end test inside the built image, with a private local HTTPS Git server.

Run with /tests mounted read-only and PYTHONPATH=/app. No external Git service
or real credentials are used. App data lives only in the disposable container.
"""

import base64
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


def git(directory, *args):
    return subprocess.run(["git", "-c", "user.name=CI", "-c", "user.email=ci@example.local", *args],
                          cwd=directory, check=True, capture_output=True, text=True).stdout.strip()


class GitContainerTest(unittest.TestCase):
    def test_authenticated_web_edit_sync_restart_and_remote_update(self):
        with tempfile.TemporaryDirectory(prefix="git-server-") as temporary:
            root = Path(temporary)
            remote = root / "recipes.git"
            writer = root / "writer"
            git(root, "init", "--bare", "--initial-branch=main", str(remote))
            git(root, "config", "--file", str(remote / "config"), "http.receivepack", "true")
            git(root, "clone", str(remote), str(writer))
            (writer / "recepten").mkdir()
            (writer / "recepten" / "soup.cook").write_text("Boil @water{1%l}.\n")
            git(writer, "add", ".")
            git(writer, "commit", "-m", "Initial recipe")
            git(writer, "push", "origin", "main")

            certificate, key = root / "cert.pem", root / "key.pem"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-keyout", str(key), "-out", str(certificate), "-days", "1",
                            "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                           check=True, capture_output=True)
            authorization = "Basic " + base64.b64encode(b"ci-user:ci-only-token").decode()
            backend = str(Path(git(root, "--exec-path")) / "git-http-backend")

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def do_GET(self):
                    self.serve_git()

                def do_POST(self):
                    self.serve_git()

                def serve_git(self):
                    if self.headers.get("Authorization") != authorization:
                        self.send_response(401)
                        self.send_header("WWW-Authenticate", 'Basic realm="Git integration test"')
                        self.end_headers()
                        return
                    url = urlsplit(self.path)
                    body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    environment = os.environ | dict(
                        GIT_PROJECT_ROOT=str(root), GIT_HTTP_EXPORT_ALL="1", REMOTE_USER="ci-user",
                        REQUEST_METHOD=self.command, PATH_INFO=url.path, QUERY_STRING=url.query,
                        CONTENT_TYPE=self.headers.get("Content-Type", ""), CONTENT_LENGTH=str(len(body)),
                        REMOTE_ADDR="127.0.0.1", SERVER_PROTOCOL="HTTP/1.1", GATEWAY_INTERFACE="CGI/1.1")
                    result = subprocess.run([backend], env=environment, input=body, capture_output=True, check=True)
                    header, body = result.stdout.split(b"\r\n\r\n", 1)
                    headers = [line.decode().split(":", 1) for line in header.split(b"\r\n")]
                    status = next((int(value.strip().split()[0]) for name, value in headers if name == "Status"), 200)
                    self.send_response(status)
                    for name, value in headers:
                        if name != "Status":
                            self.send_header(name, value.strip())
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            https = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certificate, key)
            https.socket = context.wrap_socket(https.socket, server_side=True)
            thread = threading.Thread(target=https.serve_forever, daemon=True)
            thread.start()
            app = None
            log_file = root / "app.log"
            log = log_file.open("wb")
            try:
                data = Path("/data")
                data.mkdir(exist_ok=True)
                url = f"https://127.0.0.1:{https.server_port}/recipes.git"
                (data / "options.json").write_text(json.dumps(dict(
                    users=[dict(username="ci-user", password="ci-only-web-password")],
                    sync=dict(git=dict(enabled=True, repository=url, branch="main",
                                       recipes_subdirectory="recepten", interval_seconds=10,
                                       https_username="ci-user", https_token="ci-only-token")))))
                environment = os.environ | dict(GIT_SSL_CAINFO=str(certificate))

                def start():
                    return subprocess.Popen(["/run.sh"], env=environment, stdout=log, stderr=log)

                def wait_for(predicate, description):
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        self.assertIsNone(app.poll(), "App exited:\n" + log_file.read_text(errors="replace"))
                        try:
                            if predicate():
                                return
                        except (OSError, ValueError, subprocess.CalledProcessError):
                            pass
                        time.sleep(0.2)
                    self.fail(description + "\n" + log_file.read_text(errors="replace"))

                browser = build_opener(HTTPCookieProcessor(CookieJar()))

                def read_recipe():
                    with browser.open("http://127.0.0.1:9080/api/recipes/raw/soup.cook", timeout=2) as response:
                        return response.read().decode()

                app = start()
                wait_for(lambda: "Boil" in read_recipe(), "Initial Git recipe was not served")
                login = Request("http://127.0.0.1:9080/login", data=urlencode(dict(
                    username="ci-user", password="ci-only-web-password")).encode())
                with browser.open(login, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                content = "Boil @water{2%l} for ~{5%minutes}.\n"
                save = Request("http://127.0.0.1:9080/api/recipes/soup.cook", method="PUT",
                               data=content.encode(), headers={"Content-Type": "text/plain"})
                with browser.open(save, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                wait_for(lambda: git(remote, "show", "main:recepten/soup.cook") == content.strip(),
                         "The authenticated web edit was not pushed to the private HTTPS Git server")
                self.assertNotIn("ci-only-token", (Path("/share/cooklang/git/repository/.git/config")).read_text())
                self.assertEqual((data / "sync/https.json").stat().st_mode & 0o777, 0o600)

                app.terminate()
                app.wait(timeout=20)
                app = start()
                wait_for(lambda: read_recipe() == content, "Recipe did not survive app restart")
                git(writer, "pull", "--ff-only")
                remote_content = "Boil @water{3%l}.\n"
                (writer / "recepten/soup.cook").write_text(remote_content)
                git(writer, "commit", "-am", "Remote recipe update")
                git(writer, "push", "origin", "main")
                wait_for(lambda: read_recipe() == remote_content, "The remote update was not served")
                status = json.loads(Path("/share/cooklang/sync-status.json").read_text())
                self.assertEqual(status["state"], "synced")
                self.assertNotIn("ci-only-token", log_file.read_text(errors="replace"))
            finally:
                if app is not None and app.poll() is None:
                    app.terminate()
                    try:
                        app.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        app.kill()
                        app.wait()
                log.close()
                https.shutdown()
                https.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
