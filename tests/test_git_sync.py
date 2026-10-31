"""Integration tests against real, local Git repositories; no network required."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from git_sync import GitBackend, SyncError  # noqa: E402
from git_credentials import response  # noqa: E402
from sync_service import Server  # noqa: E402


def git(directory, *args):
    env = os.environ.copy()
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.local",
               GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.local")
    return subprocess.run(["git", "-c", "core.autocrlf=false", *args],
                          cwd=directory, env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


class GitSyncTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cookcli-git-", dir=os.environ.get("COOKCLI_TEST_TMP"))
        def cleanup():
            # Windows scanners may briefly retain directory handles after Git exits.
            for attempt in range(30):
                try:
                    self.temporary.cleanup()
                    return
                except PermissionError:
                    if os.name != "nt" or attempt == 29:
                        raise
                    time.sleep(0.1)
        self.addCleanup(cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        self.writer = self.root / "writer"
        self.share = self.root / "share"
        self.data = self.root / "data"
        git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        git(self.root, "clone", str(self.remote), str(self.writer))
        (self.writer / "recepten").mkdir()
        (self.writer / "recepten" / "soup.cook").write_text("Cook @water{1%l}.\n", encoding="utf-8")
        (self.writer / "README.md").write_text("Not a recipe.\n", encoding="utf-8")
        self.publish("Initial recipes")
        self.options = dict(repository=str(self.remote), branch="main", recipes_subdirectory="recepten")
        self.backend = self.new_backend()
        self.backend.prepare()
        self.pauses = 0

    def new_backend(self):
        return GitBackend(self.options, self.share, self.data, allow_local_remote=True)

    def publish(self, message):
        git(self.writer, "add", "-A")
        git(self.writer, "commit", "-m", message)
        git(self.writer, "push", "origin", "main")

    @contextmanager
    def paused(self):
        self.pauses += 1
        yield

    def remote_text(self, name):
        return git(self.remote, "show", "main:recepten/" + name)

    def test_web_edits_additions_deletions_and_no_empty_commits(self):
        soup = self.backend.recipes / "soup.cook"
        soup.write_text("Cook @water{2%l}.\n", encoding="utf-8")
        (self.backend.recipes / "bread.cook").write_text("Bake @flour{500%g}.\n", encoding="utf-8")
        self.backend.cycle(self.paused)
        self.assertEqual(self.remote_text("soup.cook"), "Cook @water{2%l}.")
        self.assertEqual(self.remote_text("bread.cook"), "Bake @flour{500%g}.")
        head = git(self.remote, "rev-parse", "main")
        self.backend.cycle(self.paused)
        self.assertEqual(git(self.remote, "rev-parse", "main"), head)
        self.assertEqual(self.pauses, 1)
        soup.unlink()
        self.backend.cycle(self.paused)
        self.assertNotIn("soup.cook", git(self.remote, "ls-tree", "-r", "main"))

    def test_remote_update_and_independent_local_change_merge(self):
        (self.backend.recipes / "bread.cook").write_text("Bake bread.\n", encoding="utf-8")
        (self.writer / "recepten" / "soup.cook").write_text("Boil @water{3%l}.\n", encoding="utf-8")
        self.publish("Change soup remotely")
        self.backend.cycle(self.paused)
        self.assertEqual((self.backend.recipes / "soup.cook").read_text(), "Boil @water{3%l}.\n")
        self.assertEqual(self.remote_text("bread.cook"), "Bake bread.")
        self.assertEqual(len(git(self.remote, "rev-list", "--parents", "-n", "1", "main").split()), 3)

    def test_remote_updates_are_applied_without_local_edits(self):
        (self.writer / "recepten" / "soup.cook").unlink()
        (self.writer / "recepten" / "bread.cook").write_text("Bake bread.\n", encoding="utf-8")
        self.publish("Replace soup with bread")
        self.backend.cycle(self.paused)
        self.assertFalse((self.backend.recipes / "soup.cook").exists())
        self.assertEqual((self.backend.recipes / "bread.cook").read_text(), "Bake bread.\n")
        self.assertEqual(self.pauses, 1)

    def test_network_operations_run_outside_server_pause(self):
        original = self.backend.git
        is_paused = False

        @contextmanager
        def pause():
            nonlocal is_paused
            is_paused = True
            try:
                yield
            finally:
                is_paused = False

        def checked(*args, **kwargs):
            if args[0] in ("fetch", "push"):
                self.assertFalse(is_paused)
            if args[0] in ("commit", "merge"):
                self.assertTrue(is_paused)
            return original(*args, **kwargs)

        self.backend.git = checked
        (self.backend.recipes / "bread.cook").write_text("Bake bread.\n", encoding="utf-8")
        (self.writer / "recepten" / "soup.cook").write_text("Remote soup.\n", encoding="utf-8")
        self.publish("Remote change")
        self.backend.cycle(pause)

    def test_concurrent_remote_push_is_merged_on_next_cycle(self):
        original = self.backend.git
        raced = False

        def concurrent(*args, **kwargs):
            nonlocal raced
            if args[0] == "push" and not raced:
                raced = True
                (self.writer / "recepten" / "bread.cook").write_text("Remote bread.\n", encoding="utf-8")
                self.publish("Push during app sync")
            return original(*args, **kwargs)

        self.backend.git = concurrent
        (self.backend.recipes / "soup.cook").write_text("Local soup.\n", encoding="utf-8")
        with self.assertRaisesRegex(SyncError, "Cannot push"):
            self.backend.cycle(self.paused)
        self.backend.cycle(self.paused)
        self.assertEqual(self.remote_text("soup.cook"), "Local soup.")
        self.assertEqual(self.remote_text("bread.cook"), "Remote bread.")

    def test_conflict_keeps_local_recipes_and_both_commits(self):
        (self.backend.recipes / "soup.cook").write_text("Local soup.\n", encoding="utf-8")
        (self.writer / "recepten" / "soup.cook").write_text("Remote soup.\n", encoding="utf-8")
        self.publish("Remote conflict")
        with self.assertRaisesRegex(SyncError, "conflict"):
            self.backend.cycle(self.paused)
        self.assertEqual((self.backend.recipes / "soup.cook").read_text(), "Local soup.\n")
        self.assertEqual(self.remote_text("soup.cook"), "Remote soup.")
        self.assertEqual(self.backend.details["conflict_paths"], ["recepten/soup.cook"])
        git(self.backend.checkout, "rev-parse", "refs/cookcli/conflict-local")
        git(self.backend.checkout, "rev-parse", "refs/cookcli/conflict-remote")
        with self.assertRaisesRegex(SyncError, "conflict"):
            self.backend.cycle(self.paused)
        self.assertEqual(self.pauses, 1, "An unchanged conflict must not restart CookCLI repeatedly")
        restarted = self.new_backend()
        restarted.prepare()
        with self.assertRaisesRegex(SyncError, "conflict"):
            restarted.cycle(self.paused)
        self.assertNotIn("<<<<<<<", (restarted.recipes / "soup.cook").read_text())

    def test_offline_changes_are_committed_then_pushed_after_reconnect(self):
        original = self.backend.git

        def disconnected(*args, **kwargs):
            if args[0] == "fetch":
                raise SyncError("Offline")
            return original(*args, **kwargs)

        self.backend.git = disconnected
        (self.backend.recipes / "soup.cook").write_text("Offline soup.\n", encoding="utf-8")
        with self.assertRaisesRegex(SyncError, "fetch"):
            self.backend.cycle(self.paused)
        self.assertEqual(git(self.backend.checkout, "status", "--porcelain"), "")
        self.assertEqual(git(self.backend.checkout, "show", "HEAD:recepten/soup.cook"), "Offline soup.")
        restarted = self.new_backend()
        restarted.prepare()
        restarted.cycle(self.paused)
        self.assertEqual(self.remote_text("soup.cook"), "Offline soup.")

    def test_rejected_push_preserves_commits_and_retries(self):
        original = self.backend.git

        def rejected(*args, **kwargs):
            if args[0] == "push":
                return subprocess.CompletedProcess(args, 1, b"", b"SECRET")
            return original(*args, **kwargs)

        self.backend.git = rejected
        (self.backend.recipes / "soup.cook").write_text("Pending soup.\n", encoding="utf-8")
        with self.assertRaisesRegex(SyncError, "Cannot push") as error:
            self.backend.cycle(self.paused)
        self.assertNotIn("SECRET", str(error.exception))
        self.assertEqual(self.backend.details["pending_commits"], 1)
        self.backend.git = original
        self.backend.cycle(self.paused)
        self.assertEqual(self.remote_text("soup.cook"), "Pending soup.")
        self.assertEqual(self.pauses, 1, "Retrying a pending push does not need to stop CookCLI")

    def test_existing_recipes_are_never_overwritten(self):
        identity = self.data / "sync" / "identity.json"
        identity.unlink()
        legacy = self.share / "recipes"
        legacy.mkdir()
        (legacy / "precious.cook").write_text("Keep me.\n", encoding="utf-8")
        with self.assertRaisesRegex(SyncError, "Existing"):
            self.new_backend().prepare()
        self.assertEqual((legacy / "precious.cook").read_text(), "Keep me.\n")

    def test_configuration_change_does_not_reuse_checkout(self):
        self.options["branch"] = "other"
        with self.assertRaisesRegex(SyncError, "configuration changed"):
            self.new_backend().prepare()

    def test_unrelated_files_are_not_auto_committed(self):
        (self.backend.checkout / "README.md").write_text("Manual change.\n", encoding="utf-8")
        (self.backend.recipes / "soup.cook").write_text("New soup.\n", encoding="utf-8")
        with self.assertRaisesRegex(SyncError, "outside"):
            self.backend.cycle(self.paused)
        self.assertEqual(self.remote_text("soup.cook"), "Cook @water{1%l}.")

    def test_remote_symlink_is_refused_before_live_checkout_changes(self):
        # Git plumbing creates a real symlink tree entry on Windows too.
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.writer,
                              input=b"/etc/passwd", capture_output=True, check=True).stdout.decode().strip()
        git(self.writer, "update-index", "--add", "--cacheinfo", "120000," + blob + ",recepten/leak")
        git(self.writer, "commit", "-m", "Unsafe recipe symlink")
        git(self.writer, "push", "origin", "main")
        with self.assertRaisesRegex(SyncError, "symlink"):
            self.backend.cycle(self.paused)
        self.assertFalse((self.backend.recipes / "leak").exists())

    def test_status_is_machine_readable_and_outside_recipe_tree(self):
        self.backend.cycle(self.paused)
        status = json.loads((self.share / "sync-status.json").read_text())
        self.assertEqual(status["state"], "synced")
        self.assertEqual(status["pending_commits"], 0)
        self.assertTrue(status["last_success"])
        self.assertFalse((self.backend.recipes / "sync-status.json").exists())

    def test_path_and_credential_validation(self):
        for directory in ("", ".", "../recepten", "recepten/../etc", "/etc", ".git", "a\\b"):
            with self.subTest(directory=directory), self.assertRaises(SyncError):
                GitBackend(dict(self.options, recipes_subdirectory=directory), self.share, self.data,
                           allow_local_remote=True)
        for remote in ("https://user:secret@example.com/repo", "file:///tmp/repo", "-x", "https://user@example.com/repo"):
            with self.subTest(remote=remote), self.assertRaises(SyncError):
                GitBackend(dict(self.options, repository=remote), self.share, self.data)

    def test_inline_ssh_credentials_are_private_and_normalized(self):
        backend = GitBackend(dict(self.options, repository="git@example.local:recipes.git",
                                  private_key="ci-only-key\r\nsecond-line", known_hosts="example.local ci-only-host"),
                             self.share, self.data)
        key = self.data / "sync" / "ssh" / "id"
        self.assertEqual(key.read_bytes(), b"ci-only-key\nsecond-line\n")
        self.assertIn("StrictHostKeyChecking=yes", backend.env["GIT_SSH_COMMAND"])
        self.assertNotIn("ci-only-key", backend.env["GIT_SSH_COMMAND"])
        self.assertFalse((self.share / "ssh").exists())
        if os.name != "nt":
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)

    def test_https_helper_is_scoped_and_token_not_in_url_or_arguments(self):
        options = dict(self.options, repository="https://example.local/team/recipes.git",
                       https_username="ci-user", https_token="ci-only-token")
        backend = GitBackend(options, self.share, self.data)
        self.assertNotIn("ci-only-token", str(backend.git_options))
        self.assertNotIn("ci-only-token", str(backend.env))
        credentials = json.loads((self.data / "sync" / "https.json").read_text())
        request = dict(protocol="https", host="example.local", path="team/recipes.git")
        self.assertIn("password=ci-only-token", response(request, credentials))
        for change in (dict(host="other.local"), dict(path="team/other.git"),
                       dict(protocol="http"), dict(username="other-user")):
            self.assertEqual(response(request | change, credentials), "")
        result = subprocess.run(["git", *backend.git_options, "credential", "fill"],
                                env=backend.env, input="protocol=https\nhost=example.local\npath=team/recipes.git\n\n",
                                capture_output=True, text=True, check=True)
        self.assertIn("password=ci-only-token", result.stdout)
        self.assertEqual(result.stderr, "")
        # Removing a token removes the private helper copy as well.
        GitBackend(dict(options, https_token=""), self.share, self.data)
        self.assertFalse((self.data / "sync" / "https.json").exists())

    def test_server_restarts_even_when_sync_fails(self):
        server = Server([sys.executable, "-c", "import time; time.sleep(60)"])
        server.start()
        original = server.process
        try:
            with self.assertRaisesRegex(SyncError, "example"):
                with server.paused():
                    self.assertIsNotNone(original.poll())
                    raise SyncError("example")
            self.assertIsNone(server.process.poll())
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
