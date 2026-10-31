"""Git backend. Only the coordinator may pause/resume the recipe writer."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


class SyncError(Exception):
    """Safe, credential-free message suitable for the app log."""


class SyncConflict(SyncError):
    """Both heads are retained and require a human merge."""


def fingerprint(root):
    """Include deletions, new files and images; never follow symlinks."""
    result = {}
    if root.is_symlink():
        raise SyncError("The recipe directory must not be a symlink.")
    if not root.exists():
        return result
    for directory, directories, files in os.walk(root):
        for name in directories + files:
            path = Path(directory) / name
            if path.is_symlink() or name == ".git":
                raise SyncError("Symlinks and nested Git repositories are not supported in recipes.")
        for name in files:
            path = Path(directory) / name
            if not path.is_file():
                raise SyncError("Recipes may only contain regular files.")
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class GitBackend:
    name = "git"

    def __init__(self, options, share, data, *, allow_local_remote=False):
        self.options = options
        self.share = Path(share)
        self.data = Path(data) / "sync"
        self.checkout = self.share / "git" / "repository"
        self.merge_path = self.data / "merge"
        self.branch = options.get("branch", "main")
        self.remote = options.get("repository", "")
        if any(character.isspace() for character in self.remote):
            raise SyncError("The repository URL must not contain whitespace.")
        self.subdir = options.get("recipes_subdirectory", "recepten")
        path = PurePosixPath(self.subdir)
        if (not self.subdir or path.is_absolute() or "\\" in self.subdir
                or any(part in ("", ".", "..", ".git") for part in self.subdir.split("/"))):
            raise SyncError("Set recipes_subdirectory to a relative directory inside the repository.")
        if (not self.branch or self.branch.startswith("-")
                or subprocess.run(["git", "check-ref-format", "--branch", self.branch],
                                  capture_output=True).returncode):
            raise SyncError("Invalid Git branch.")
        try:
            url = urlsplit(self.remote)
        except ValueError as exc:
            raise SyncError("Invalid repository URL.") from exc
        ssh_style = re.fullmatch(r"[\w.-]+@[\w.-]+:[^\s]+", self.remote)
        if not allow_local_remote:
            if not (url.scheme in ("ssh", "https") and url.hostname or ssh_style):
                raise SyncError("Use an SSH or HTTPS repository URL.")
            if url.password or url.query or url.fragment or (url.scheme == "https" and url.username):
                raise SyncError("Do not include credentials, query strings or fragments in the repository URL.")
        self.recipes = self.checkout.joinpath(*path.parts)
        self.interval = options.get("interval_seconds", 60)
        if not isinstance(self.interval, int) or not 10 <= self.interval <= 86400:
            raise SyncError("Git sync interval must be between 10 and 86400 seconds.")
        self.data.mkdir(parents=True, exist_ok=True)
        self.data.chmod(0o700)
        self.env = os.environ.copy()
        self.env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_MERGE_AUTOEDIT="no", GIT_ASKPASS="false")
        self.git_options = ["-c", "core.hooksPath=" + str(self.data / "no-hooks"),
                            "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
                            "-c", "credential.helper=",
                            "-c", "protocol.file.allow=" + ("always" if allow_local_remote else "never")]
        self.ssh = url.scheme == "ssh" or bool(ssh_style)
        token = options.get("https_token", "")
        if token:
            if url.scheme != "https":
                raise SyncError("https_token requires an HTTPS repository URL.")
            username = options.get("https_username", "git")
            if not username or any(c in username + token for c in "\r\n\0"):
                raise SyncError("HTTPS username and token must be non-empty single-line values.")
            credentials = self.data / "https.json"
            credentials.touch(mode=0o600, exist_ok=True)
            credentials.chmod(0o600)
            credentials.write_text(json.dumps(dict(repository=self.remote, username=username, token=token)), encoding="utf-8")
            self.env["COOKCLI_GIT_CREDENTIALS"] = str(credentials)
            helper = Path(__file__).with_name("git_credentials.py")
            self.git_options += ["-c", "credential.useHttpPath=true", "-c",
                                 "credential.helper=!" + shlex.quote(Path(sys.executable).as_posix())
                                 + " " + shlex.quote(helper.as_posix())]
        else:
            (self.data / "https.json").unlink(missing_ok=True)
        if self.ssh:
            self._ssh_credentials()
        self.last_success = None
        previous_status = self.data / "status.json"
        if previous_status.exists():
            try:
                self.last_success = json.loads(previous_status.read_text()).get("last_success")
            except (OSError, ValueError, AttributeError):
                pass
        self.last_status = None
        self.details = {}
        self.conflict_pair = None

    def _ssh_credentials(self):
        ssh_dir = self.data / "ssh"
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        ssh_dir.chmod(0o700)
        for setting, inline, name in (("private_key_file", "private_key", "id"),
                                      ("known_hosts_file", "known_hosts", "known_hosts")):
            content = self.options.get(inline, "")
            source = Path(self.options.get(setting, ""))
            # Both configured inputs live outside the served recipe tree.
            if content:
                value = (content.replace("\r\n", "\n").rstrip("\n") + "\n").encode("utf-8")
            else:
                try:
                    valid = (source.is_absolute() and source.is_file()
                             and source.resolve().is_relative_to(self.share.resolve() / "ssh"))
                except OSError:
                    valid = False
                if not valid:
                    raise SyncError("Configure private_key and known_hosts, or their file paths under /share/cooklang/ssh/.")
                value = source.read_bytes()
            target = ssh_dir / name
            target.touch(mode=0o600, exist_ok=True)
            target.chmod(0o600)
            target.write_bytes(value)
        self.env["GIT_SSH_COMMAND"] = " ".join([
            "ssh", "-F", shlex.quote(os.devnull), "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=15", "-o", "GlobalKnownHostsFile=" + shlex.quote(os.devnull),
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
            "-o", "UserKnownHostsFile=" + shlex.quote(str(ssh_dir / "known_hosts")),
            "-i", shlex.quote(str(ssh_dir / "id")),
        ])

    def git(self, *args, cwd=None, check=True):
        try:
            result = subprocess.run(["git", *self.git_options, *args],
                                    cwd=cwd or self.checkout, env=self.env,
                                    capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SyncError("Git operation failed or timed out; local recipes are retained.") from exc
        if check and result.returncode:
            # Git stderr can contain repository URLs and authentication details.
            raise SyncError("Git operation failed; check connectivity, branch, SSH trust and repository permissions.")
        return result

    def value(self, *args, cwd=None):
        return self.git(*args, cwd=cwd).stdout.decode().strip()

    def status(self, state, message, **extra):
        payload = dict(backend=self.name, state=state, message=message,
                       last_success=self.last_success, **(self.details | extra))
        for path in (self.data / "status.json", self.share / "sync-status.json"):
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
        if (state, message) != self.last_status:
            print(f"CookCLI sync [{state}]: {message}", flush=True)
            self.last_status = (state, message)

    def validate_tree(self, revision, *, cwd=None):
        entries = self.git("ls-tree", "-r", "-z", revision, cwd=cwd).stdout.split(b"\0")
        for entry in filter(None, entries):
            metadata, raw_path = entry.split(b"\t", 1)
            try:
                name = raw_path.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SyncError("Repository filenames must be valid UTF-8.") from exc
            relevant = (name == self.subdir or name.startswith(self.subdir + "/")
                        or self.subdir.startswith(name + "/"))
            if name == self.subdir or self.subdir.startswith(name + "/"):
                raise SyncError("recipes_subdirectory must point to a directory, not a file.")
            if relevant and metadata.split()[0] not in (b"100644", b"100755"):
                raise SyncError("The remote recipe tree contains a symlink or submodule; sync is paused.")

    def prepare(self):
        identity = dict(repository=self.remote, branch=self.branch, subdirectory=self.subdir)
        identity_file = self.data / "identity.json"
        if identity_file.exists() and json.loads(identity_file.read_text()) != identity:
            raise SyncError("Git configuration changed. Restore the previous settings or migrate the checkout manually.")
        if not self.checkout.exists():
            self.checkout.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix="clone-", dir=self.checkout.parent))
            try:
                self.git("clone", "--no-checkout", "--single-branch", "--branch", self.branch,
                         "--", self.remote, str(temporary), cwd=self.checkout.parent)
                self.validate_tree("HEAD", cwd=temporary)
                self.git("checkout", "--force", self.branch, cwd=temporary)
                temporary.rename(self.checkout)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        if self.value("remote", "get-url", "origin") != self.remote:
            raise SyncError("The checkout remote differs from the configured repository.")
        if self.value("symbolic-ref", "--short", "HEAD") != self.branch:
            raise SyncError("The checkout branch differs from the configured branch.")
        self.validate_tree("HEAD")
        if self.git("rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0:
            raise SyncError("The active checkout has an unfinished merge; resolve it before syncing.")
        self.recipes.mkdir(parents=True, exist_ok=True)
        self.snapshot()
        if not identity_file.exists():
            existing = fingerprint(self.share / "recipes")
            if existing and existing != fingerprint(self.recipes):
                raise SyncError("Existing /share/cooklang/recipes differs from Git. Commit those recipes to Git first, or move that folder aside after backing it up.")
            identity_file.write_text(json.dumps(identity), encoding="utf-8")
        for setting, default in (("author_name", "Home Assistant"),
                                 ("author_email", "home-assistant@localhost")):
            value = self.options.get(setting, default)
            if not value or "\n" in value or "\r" in value:
                raise SyncError("Git author name and email must be non-empty single-line values.")
            self.git("config", "user." + ("name" if setting == "author_name" else "email"), value)

    def _local_changes(self):
        return bool(self.git("status", "--porcelain", "--untracked-files=all", "--", ":(literal)" + self.subdir).stdout)

    def snapshot(self):
        for directory in (self.recipes, *self.recipes.parents):
            if directory.is_symlink():
                raise SyncError("The recipe directory and its parents must not be symlinks.")
            if directory == self.checkout:
                break
        return fingerprint(self.recipes)

    def cycle(self, pause):
        """No network I/O while the web writer is paused. Never force-push."""
        # Save local changes even if fetching fails: commits are a local history too.
        try:
            fetch = self.git("fetch", "--no-tags", "origin", self.branch, check=False)
            online = fetch.returncode == 0
        except SyncError:
            online = False
        remote_head = self.value("rev-parse", "FETCH_HEAD") if online else self.value("rev-parse", "refs/remotes/origin/" + self.branch)
        local_head = self.value("rev-parse", "HEAD")
        changed = self._local_changes()
        if not changed and (local_head, remote_head) == self.conflict_pair:
            raise SyncConflict("Git conflict persists; resolve the conflicting recipe changes manually.")
        needs_merge = online and self.git("merge-base", "--is-ancestor", remote_head, local_head, check=False).returncode != 0
        if changed or needs_merge:
            with pause():
                self.snapshot()
                # Do not publish unrelated edits made through Samba or a shell.
                outside = self.git("status", "--porcelain", "--untracked-files=all", "--", ".",
                                   ":(exclude,literal)" + self.subdir).stdout
                if outside:
                    raise SyncError("The checkout has changes outside the recipes directory; resolve them manually.")
                if self._local_changes():
                    self.git("add", "-A", "--", ":(literal)" + self.subdir)
                if self.git("diff", "--cached", "--quiet", check=False).returncode:
                    self.git("commit", "-m", "Update recipes from Home Assistant")
                self.recipes.mkdir(parents=True, exist_ok=True)
                local_head = self.value("rev-parse", "HEAD")
                self.details["local_commit"] = local_head
                self.details["remote_commit"] = remote_head
                self.details["pending_commits"] = int(self.value("rev-list", "--count", remote_head + "..HEAD"))
                if needs_merge:
                    self._merge(local_head, remote_head)
        if not online:
            raise SyncError("Cannot fetch from Git; local changes remain committed and will be retried.")
        head = self.value("rev-parse", "HEAD")
        self.details["local_commit"] = head
        self.details["remote_commit"] = remote_head
        self.details["pending_commits"] = int(self.value("rev-list", "--count", remote_head + "..HEAD"))
        if head != remote_head:
            pushed = self.git("push", "origin", "HEAD:refs/heads/" + self.branch, check=False)
            if pushed.returncode:
                raise SyncError("Cannot push to Git; local commits are retained. Sync will retry without force-pushing.")
        self.last_success = datetime.now(timezone.utc).isoformat()
        self.details = dict(local_commit=head, remote_commit=head, pending_commits=0)
        self.status("synced", "Recipes synchronized with Git.", commit=head)

    def _merge(self, local_head, remote_head):
        pair = (local_head, remote_head)
        if pair == self.conflict_pair:
            raise SyncConflict("Git conflict persists; resolve the conflicting recipe changes manually.")
        self.validate_tree(remote_head)
        # An interrupted merge is disposable: the authoritative local commit is in
        # the active checkout. Never merge conflict markers into served recipes.
        if self.merge_path.exists():
            self.git("worktree", "remove", "--force", str(self.merge_path))
        self.git("worktree", "prune")
        self.git("worktree", "add", "--detach", str(self.merge_path), local_head)
        try:
            merged = self.git("merge", "--no-edit", remote_head, cwd=self.merge_path, check=False)
            if merged.returncode:
                paths = self.git("diff", "--name-only", "--diff-filter=U", "-z", cwd=self.merge_path).stdout
                if not paths:
                    raise SyncError("Git could not merge the histories; local commits are retained. Check for rewritten or unrelated remote history.")
                self.conflict_pair = pair
                self.git("update-ref", "refs/cookcli/conflict-local", local_head)
                self.git("update-ref", "refs/cookcli/conflict-remote", remote_head)
                self.details["conflict_paths"] = [path.decode("utf-8") for path in paths.split(b"\0") if path]
                raise SyncConflict("Git conflict: both versions are retained in Git. Resolve the conflict manually; local recipes remain available.")
            result = self.value("rev-parse", "HEAD", cwd=self.merge_path)
            self.validate_tree(result, cwd=self.merge_path)
            self.git("merge", "--ff-only", result)
            self.recipes.mkdir(parents=True, exist_ok=True)
            self.conflict_pair = None
        finally:
            self.git("worktree", "remove", "--force", str(self.merge_path))
