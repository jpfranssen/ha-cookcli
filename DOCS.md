# CookCLI user guide

## Open the web interface

Start the app and open `http://<home-assistant-ip>:9080` in your browser. If you change the host port under **Network**, use that port instead.

The interface uses its own port and accounts. Home Assistant ingress and automatic Home Assistant sign-in are not currently available. Start with the IP address rather than a hostname if you have connection problems.

### Access through a hostname

CookCLI accepts IP addresses by default. To use `http://homeassistant.local:9080`, open the app's **Configuration** tab and set **Trusted web origin** (`cors_origin`):

```yaml
cors_origin: "http://homeassistant.local:9080"
```

Keep your existing `users` configuration, save and restart the app. Use the exact origin from your browser: scheme (`http` or `https`), hostname and port, without a path or trailing slash. If you change the host port, update this setting too. Leave it empty when using only an IP address.

The setting passes `--cors-origin` to CookCLI and preserves its CSRF and DNS rebinding protection. An explicit origin is required because an arbitrary hostname could resolve to your server. See the [upstream server documentation](https://github.com/cooklang/cookcli#cook-server).

## Configure users

Open the app's **Configuration** tab. Add users through the form or use YAML:

```yaml
users:
  - username: alice
    password: "replace-with-your-own-password"
  - username: bob
    password: "replace-with-a-different-password"
```

Save your changes and **restart the app**. New accounts are created and changed passwords are updated at startup. Unchanged passwords are not reset.

Usernames are case-sensitive and must contain 1 to 32 characters: letters `a-z` and `A-Z`, digits, `_` or `-`. Use unique usernames and a non-empty password on a single line.

Once an account exists, visitors can browse recipes and users must sign in to make changes. All configured accounts have write access; this app does not provide separate roles. These accounts are separate from your Home Assistant and Samba accounts.

**On a fresh installation with `users: []`, anyone who can reach the web interface can make changes.** Configure a user before the first start if you want to require sign-in. This is [CookCLI's authentication behavior](https://github.com/cooklang/cookcli#cook-server).

### Change a password

Update the password for the existing username in the app configuration, save and restart the app.

### Remove or rename a user

Removing a user from the app configuration does **not** delete their CookCLI account. Setting `users: []` does not remove existing accounts either. Changing a username creates another account and leaves the old account in place.

Currently, deleting an account requires running `cook server user remove <username>` **inside the CookCLI container**, with `COOK_CONFIG_DIR=/data/cookcli`. A regular Home Assistant terminal runs in a different container. Also remove the user from the app configuration, or the account will be recreated at the next start.

## Add recipes

The app creates this directory at first start:

```text
/share/cooklang/recipes
```

Place your `.cook` files there. Subfolders can be used to organize recipes:

```text
share/
└── cooklang/
    └── recipes/
        ├── Tomato pasta.cook
        └── Soups/
            └── Tomato soup.cook
```

With Home Assistant's **Samba share** app, Windows users can open `\\<home-assistant-ip>\share\cooklang\recipes`. Sign in with your Samba credentials. An editor in another app can access this directory only if that app has access to `share`.

You can also manage recipes through CookCLI's web interface. Sign in using a configured account to make changes. Refresh the page if newly added files are not visible.

### Example recipe

Save this as UTF-8 in `Tomato pasta.cook`:

```cooklang
---
title: Tomato pasta
servings: 2
---

Cook @pasta{200%g} in a #pot{} of @water{}.

Heat @olive oil{1%tbsp} in a #frying pan{} and briefly fry @garlic{1%clove}.

Add @chopped tomatoes{400%g} and simmer for ~{10%minutes}.

Combine the pasta and sauce, then season with @salt{} and @pepper{}.
```

In Cooklang, `@` marks an ingredient, `#` marks cookware and `~` marks a timer. Quantities and units go inside braces, separated by `%`. See the [Cooklang syntax reference](https://cooklang.org/docs/spec/) for details.

Without Git sync the recipe directory remains `/share/cooklang/recipes`.

## Git synchronization

Git sync is optional and disabled by default. It connects directly to a Git server, including self-hosted Forgejo, Gitea or GitLab. No Cook Cloud account is involved.

### GitHub: configure an HTTPS token

For GitHub, use the repository's normal HTTPS clone URL and enter a personal access token in the app's **HTTPS access token** field. Set **HTTPS username** to your GitHub username. Create a fine-grained token limited to this recipe repository with **Contents: Read and write**, and allow that user to push to the configured branch. See GitHub's [token documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

Add these fields to `sync.git` alongside the branch, recipe directory and other settings below:

```yaml
repository: "https://github.com/your-username/recipes.git"
https_username: your-username
https_token: !secret cookcli_git_token
```

Alternatively, enter the token directly into the masked configuration field. The `password` field masks the form; it does not encrypt the Home Assistant options file or backups. The app writes its runtime token copy under `/data/sync/https.json` with mode `0600`. A repository-scoped Git credential helper supplies it only for the configured HTTPS host and repository path. Tokens are not added to remote URLs, command-line arguments, recipe files or app logs. Removing `https_token` removes that runtime copy on the next start. Other Git servers can use the same HTTPS username/token settings.

### SSH: configure a private key

SSH keys can also be entered directly in the app configuration. Use the YAML editor for multiline input, or a Home Assistant `!secret` reference:

```yaml
private_key: !secret cookcli_git_private_key
known_hosts: |
  git.example.local ssh-ed25519 REPLACE_WITH_VERIFIED_PUBLIC_HOST_KEY
```

To paste the private key directly, use `private_key: |` followed by the complete indented key, including its BEGIN/END lines. Inline values override the corresponding file input. The app normalizes inline line endings and writes restricted runtime copies under `/data/sync/ssh/`. The key field is masked in the form. Configuration and backups can contain credentials even with a secret reference, because Home Assistant resolves secrets into app options at startup.

### Prepare the repository and file-based SSH access

1. Use an existing repository with at least one commit on the configured branch. Keep recipes in a subdirectory such as `recepten/`; the repository root cannot be served. Images, menu files and recipe configuration inside that directory are synchronized too. Git ignore rules apply.
2. Create a dedicated SSH key without a passphrase and grant its public key write access to this repository on your Git server. The configured branch must permit direct pushes by that key.
3. Place the private key at `/share/cooklang/ssh/id_ed25519`, and a `known_hosts` file containing your Git server's verified public host key at `/share/cooklang/ssh/known_hosts`. For a nonstandard SSH port, use the `[hostname]:port` known-hosts notation.
4. Verify the host-key fingerprint against the Git server administrator or its local configuration. Do not trust an unverified `ssh-keyscan` result. Host-key checking is mandatory; the app never accepts an unknown host automatically.

If you prefer file inputs, copy them through Samba, for example into `\\<home-assistant-ip>\share\cooklang\ssh`. Limit access to the share because it contains the original private key. The app copies these inputs into private app data with restricted permissions at startup; neither is inside the served recipes directory. Encrypted SSH keys are not supported.

### Configure Git

Keep your existing `users` and `cors_origin` settings and add:

```yaml
sync:
  git:
    enabled: true
    repository: "ssh://git@git.example.local/username/recipes.git"
    branch: main
    recipes_subdirectory: recepten
    interval_seconds: 60
    author_name: Home Assistant
    author_email: home-assistant@example.local
    private_key_file: /share/cooklang/ssh/id_ed25519
    known_hosts_file: /share/cooklang/ssh/known_hosts
```

Use your Git server's clone URL, including its port if needed, for example `ssh://git@git.example.local:2222/username/recipes.git`. The `git@hostname:username/recipes.git` form also works with the default SSH port. For HTTPS, replace `repository` and add the username/token fields shown above; SSH fields are then unused. Do not put tokens or passwords in the repository URL. Optional key input files must be under `/share/cooklang/ssh/`. Restart after changing credentials.

Save and restart. Git mode checks out the repository at `/share/cooklang/git/repository` and serves only its configured recipe subdirectory, for example `/share/cooklang/git/repository/recepten`. The checkout's `.git` directory, other repository files and sync status are outside the web recipe tree. Only changes within `recipes_subdirectory` are automatically committed. Symlinks, submodules and nested Git repositories are not supported inside recipes.

**Existing installations:** `/share/cooklang/recipes` is never deleted or overwritten. On first setup, a non-empty old directory must match the Git recipes exactly. If it differs, setup stops: first incorporate those files into the repository, or back up and move the old directory aside. Once Git mode is configured, edit the Git recipe directory or use the web interface; the old directory is no longer active.

Changing the repository, branch or recipe subdirectory after setup requires manual migration. The app refuses to repurpose an existing checkout. Stop the app, preserve all unpushed work and back up both app data and the share before moving the old checkout and `/data/sync` aside for a fresh setup. That app-data path is inside the CookCLI container, not a normal HA terminal. To disable sync, set `enabled: false`; CookCLI then returns to the original local directory, which is not automatically updated from Git mode.

### Behavior and status

Every interval, the coordinator checks whether recipe files have been stable for two seconds. If they keep changing, it waits until a later cycle. It fetches remote changes, briefly stops CookCLI, commits local changes and merges in an isolated worktree. Successful merges are applied while CookCLI is stopped, and the web server restarts even after a sync error. Fetch and push operations run while the web interface is available. Unchanged collections do not cause empty commits or server restarts.

CookCLI 0.39.0 handles SIGTERM with graceful shutdown. If it does not exit within 15 seconds (for example because a connection stays open), the coordinator terminates it, restarts it and skips the local sync operation. Close the recipe editor and retry if this persists. A page may briefly lose its connection during a sync that changes files. Unsaved browser text has not reached Git; check that the editor has saved before leaving the page.

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

### Future phone synchronization

Git synchronization and phone file transport are separate concerns. This version provides the Git backend and a server coordinator; it does not configure Syncthing or any phone app. A future phone transport must join the coordinator's write/pause boundary so incoming phone writes cannot race with Git checkout updates. For now, make edits through CookCLI. Concurrent Samba edits or an independent sync daemon writing into the active checkout are not coordinated.

## Storage and backups

| Data | Path inside the CookCLI app |
| --- | --- |
| Recipes | `/share/cooklang/recipes` |
| Git checkout, including unpushed commits | `/share/cooklang/git/repository` |
| Git-mode recipes | `/share/cooklang/git/repository/<recipes_subdirectory>` |
| Git identity, runtime credentials and merge worktree | `/data/sync` |
| Public sync status | `/share/cooklang/sync-status.json` |
| CookCLI configuration and accounts | `/data/cookcli` |
| Managed password fingerprints (SHA-256) | `/data/managed-users.tsv` |

Data persists across normal restarts. Include both **CookCLI app data** and the **share** folder in your Home Assistant backups. Backing up app data alone does not include your recipes.

### Move from a local installation

A repository installation has a different internal app ID from a local installation. Configure users again in the new app; recipes remain in the shared folder. Stop the old app before starting the new one so port `9080` is available.

## Troubleshooting

- **CookCLI is missing from the store:** check that your device uses `amd64`, refresh the store and check the Supervisor logs for repository loading errors.
- **Installation fails:** check the build output in the Supervisor logs. Installation needs internet access to download the CookCLI base image and packages.
- **The web interface does not open:** check that the app is running and confirm the configured host port. Try your Home Assistant IP address instead of a hostname.
- **CookCLI reports an untrusted hostname:** configure `cors_origin` as described above, or connect using the IP address.
- **Sign-in fails:** check username capitalization, save the configuration and restart the app. Check the app log for account creation or password update errors.
- **No recipes are visible:** check that the files have a `.cook` extension and are under `/share/cooklang/recipes`, rather than `/config`.
- **Git mode shows different recipes:** it serves the configured subdirectory under `/share/cooklang/git/repository`, not the old local recipe directory.
- **Git cannot connect or push:** verify the clone URL, branch, token or SSH key, verified SSH host keys when applicable, and write access to the branch. Consult the Git server logs; raw Git authentication output is deliberately omitted from app logs.
