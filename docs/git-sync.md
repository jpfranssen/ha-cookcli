# Git synchronization

Git sync is optional. It commits saved recipe edits, pulls remote changes and pushes to your recipe repository. Start with [local recipes](../DOCS.md#start-here) if you are setting up CookCLI for the first time.

## Connect a GitHub repository

1. Prepare a recipe repository with at least one commit on the branch you want to use. Put your recipes in a subdirectory such as `recepten/`. If you already have local recipes, read [first sync and existing recipes](#first-sync-and-existing-recipes) before enabling sync.
2. Create a fine-grained GitHub personal access token for that repository with **Contents: Read and write**. The account must be allowed to push directly to the selected branch. See [GitHub's token setup guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token).
3. Open **CookCLI → Configuration** in Home Assistant and switch to YAML editing. Replace the `sync` section with the example below, keeping your existing `users` and `cors_origins` settings. Replace the repository URL, branch and folder if yours differ. Use your GitHub username and token.

```yaml
sync:
  git:
    enabled: true
    repository: "https://github.com/your-user/your-recipes.git"
    branch: main
    recipes_subdirectory: recepten
    interval_seconds: 60
    author_name: "Home Assistant"
    author_email: "home-assistant@example.local"
    https_username: "your-user"
    https_token: "replace-with-your-github-token"
```

4. Save and restart CookCLI. Check the **Log** tab for `CookCLI Git recipes:` followed by the active path. Open **Web UI** to confirm the Git recipes are visible.
5. Save a recipe edit, wait for the next sync cycle and check for `CookCLI sync [synced]` in the log. Verify that the branch on GitHub contains the change.

Enter credentials in the app configuration. Use a plain clone URL without embedded credentials. You can use a Home Assistant secret reference such as `!secret cookcli_git_token` in place of the token value. The form masks the token, and Home Assistant options and backups can contain the resolved value. The app keeps its runtime copy in `/data/sync/https.json` with restricted permissions and supplies it only for the configured HTTPS repository.

## Connect over SSH

Use a dedicated key without a passphrase and grant its public key write access to the repository. Save its private key and the Git server's verified host key under `/share/cooklang/ssh/`. Verify the server's public host-key fingerprint before adding it to `known_hosts`. For a nonstandard SSH port, use `[hostname]:port` in `known_hosts`.

```yaml
sync:
  git:
    enabled: true
    repository: "ssh://git@git.example.local/username/recipes.git"
    branch: main
    recipes_subdirectory: recepten
    interval_seconds: 60
    author_name: "Home Assistant"
    author_email: "home-assistant@example.local"
    private_key_file: "/share/cooklang/ssh/id_ed25519"
    known_hosts_file: "/share/cooklang/ssh/known_hosts"
```

For SSH on a custom port, use a URL such as `ssh://git@git.example.local:2222/username/recipes.git`. The `git@hostname:username/recipes.git` form works with the default SSH port. Inline `private_key` and `known_hosts` values override the files. Use YAML multiline blocks or Home Assistant secret references. The app copies the key and host keys into its private data folder at startup. The original files remain in the shared folder when you use file inputs.

## First sync and existing recipes

Git sync checks out the branch at `/share/cooklang/git/repository`. CookCLI serves only the configured subdirectory, for example `/share/cooklang/git/repository/recepten`. It syncs recipe files, images, menus and other files in that directory, subject to Git ignore rules. The repository root, symlinks, submodules and nested Git repositories cannot be used as recipes.

Before first enabling sync, put any existing files from `/share/cooklang/recipes` into the Git recipes directory and push them. A non-empty local recipes directory must match the Git recipes exactly, or startup stops with an error. If you want the Git copy to replace what you see in CookCLI, back up and move the old local directory aside before enabling sync. The app leaves that local directory intact when switching modes.

If setup fails, set `sync.git.enabled: false` and restart to open your local library while you resolve the error. Review the active recipe directory before editing files directly through Samba.

## Change or disable Git sync

Changing the repository, branch or recipe subdirectory after setup requires manual migration. The app refuses to repurpose an existing checkout. Stop the app, preserve all unpushed work and back up both app data and the share before moving the old checkout and `/data/sync` aside for a fresh setup. That app-data path is inside the CookCLI container, not a normal HA terminal. To disable sync, set `enabled: false`; CookCLI then returns to the original local directory, which is not automatically updated from Git mode.

## Sync status and recovery

### Behavior and status

Every interval, the coordinator checks whether recipe files have been stable for two seconds. If they keep changing, it waits until a later cycle. It fetches remote changes, briefly stops CookCLI, commits local changes and merges in an isolated worktree. Successful merges are applied while CookCLI is stopped, and the web server restarts even after a sync error. Fetch and push operations run while the web interface is available. Unchanged collections do not cause empty commits or server restarts.

CookCLI handles SIGTERM with graceful shutdown. If it does not exit within 15 seconds (for example because a connection stays open), the coordinator terminates it, restarts it and skips the local sync operation. Close the recipe editor and retry if this persists. A page may briefly lose its connection during a sync that changes files. Unsaved browser text has not reached Git; check that the editor has saved before leaving the page.

- Offline: local edits are committed in the checkout and retried later. The first clone needs connectivity; an existing checkout can start offline.
- Rejected push or concurrent remote push: local commits remain; the next cycle fetches and retries. The app never force-pushes.
- Conflict: both commits are retained, local recipes stay usable, and the active recipe files never receive merge conflict markers. An unchanged conflict does not repeatedly restart CookCLI within a running session.
- Changes outside the recipe subdirectory block a local sync rather than being committed automatically. Do not manually stage unrelated files in this checkout.

The **Log** tab reports state changes. Machine-readable status is written to `/share/cooklang/sync-status.json` and `/data/sync/status.json`, outside the recipe tree. It includes the last successful sync, known commit IDs, pending commit count when available and conflicting paths. There is no Home Assistant status entity or conflict editor yet.

### Resolve a conflict

1. Stop the CookCLI app so it cannot change or push recipes during recovery.
2. Open `/share/cooklang/git/repository` using a Git-capable machine (for example through its Samba path).
3. Ensure that machine has its own Git authentication. Run `git fetch origin`, then `git merge origin/main` (substitute your configured branch).
4. Resolve the conflicts in the recipes, stage those resolutions and create the merge commit. Push the configured branch normally, then restart the app.

Local edits made after the conflict may still be uncommitted: inspect `git status` and commit them before merging. The app retains the original conflicting commits under `refs/cookcli/conflict-local` and `refs/cookcli/conflict-remote` for recovery. It does not apply an automatic local-wins or remote-wins policy. Do not resolve conflicts in `/data/sync/merge`; that temporary worktree is disposable.

Make edits through CookCLI to coordinate them with sync. Concurrent edits through Samba or an independent file sync tool can race with Git updates.
