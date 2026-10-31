"""Coordinator for a recipe server and an optional sync backend.

Future phone transports must coordinate writes through the same pause boundary.
They must not run an independent Git checkout over this directory.
"""

from contextlib import contextmanager
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from git_sync import GitBackend, SyncConflict, SyncError


class Server:
    def __init__(self, command):
        self.command = command
        self.process = None
        self.stopping = threading.Event()

    def start(self):
        if not self.stopping.is_set():
            self.process = subprocess.Popen(self.command)

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired as exc:
                self.process.kill()
                self.process.wait()
                raise SyncError("CookCLI did not stop cleanly; no merge was attempted.") from exc

    def shutdown(self, *_):
        self.stopping.set()

    @contextmanager
    def paused(self):
        try:
            if self.stopping.is_set():
                raise SyncError("Shutdown requested; synchronization is deferred.")
            self.stop()
            yield
        finally:
            self.start()


def main():
    options = json.loads(Path("/data/options.json").read_text())
    backend = GitBackend(options["sync"]["git"], "/share/cooklang", "/data")
    try:
        backend.prepare()
    except (SyncError, OSError) as exc:
        backend.status("error", str(exc) if isinstance(exc, SyncError) else "Cannot initialize Git storage.")
        return 1
    command = sys.argv[1:]
    command[2] = str(backend.recipes)
    print(f"CookCLI Git recipes: {backend.recipes}", flush=True)
    server = Server(command)
    signal.signal(signal.SIGTERM, server.shutdown)
    signal.signal(signal.SIGINT, server.shutdown)
    server.start()
    try:
        while not server.stopping.is_set():
            if server.process.poll() is not None:
                return server.process.returncode or 1
            try:
                before = backend.snapshot()
                if server.stopping.wait(2):
                    break
                if before != backend.snapshot():
                    backend.status("pending", "Recipes are being edited; sync will retry after they settle.")
                else:
                    backend.cycle(server.paused)
            except (SyncError, OSError) as exc:
                backend.status("conflict" if isinstance(exc, SyncConflict) else "error",
                               str(exc) if isinstance(exc, SyncError) else "Cannot access recipe or sync storage; local data is retained.")
            deadline = time.monotonic() + backend.interval
            while not server.stopping.wait(0.5) and time.monotonic() < deadline:
                if server.process.poll() is not None:
                    return server.process.returncode or 1
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SyncError as exc:
        print(f"CookCLI sync [error]: {exc}", flush=True)
        sys.exit(1)
