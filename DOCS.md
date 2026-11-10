# CookCLI user guide

## Start here

1. Under **Configuration → Users**, add a CookCLI username and password and save.
2. Start the app and select **Open Web UI** on its Home Assistant app page.
3. Sign in to CookCLI and create a recipe or [add an existing recipe file](#add-recipes). Turn on **Show in sidebar** if you want the **Recepten** shortcut.

Home Assistant controls access through Ingress. Sign in with a CookCLI account to make recipe changes when account protection is enabled.

## Direct access for API clients

New installations use Ingress with the host port disabled. To connect the [CookCLI integration](https://github.com/cooklang/homeassistant-cookcli) or another API client, open **Configuration → Network**, enable **Show disabled ports**, and enter a host port for `9080/tcp`. Save and restart the app. Use `http://<home-assistant-ip>:9080` as the server URL, substituting your chosen port.

Home Assistant keeps saved port mappings when updating. If you previously used the old default port and direct access stops after updating, enable it using the same steps.

### Access through a hostname

CookCLI accepts IP addresses by default. If CookCLI rejects a hostname or browser origin, add the exact browser origin to `cors_origins` in the app's **Configuration** tab. For example, the first entry below is for direct HTTP access and the second is for Ingress through a Home Assistant instance opened at `http://homeassistant.local:8123`.

```yaml
cors_origins:
  - "http://homeassistant.local:9080"
  - "http://homeassistant.local:8123"
```

Use the scheme, hostname and port from your browser's address. Omit the path, including any Ingress path, and the trailing slash. Keep your existing `users` configuration, save and restart the app. The default is `cors_origins: []`.

When upgrading from `0.3.0` or earlier, replace the single `cors_origin` setting with a `cors_origins` list and copy the old value into it. Each entry is passed to CookCLI as a `--cors-origin` argument. CSRF and DNS rebinding checks remain enabled. See the [upstream server documentation](https://github.com/cooklang/cookcli#cook-server).

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

To connect an existing recipe repository, use the [Git synchronization guide](https://github.com/jpfranssen/ha-cookcli/blob/main/docs/git-sync.md). It includes a complete GitHub setup, SSH configuration, recipe migration and conflict recovery.

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
- **Ingress opens but links fail:** check the app log for `CookCLI: Ingress lookup failed`. The app needs the Ingress path from the Supervisor to generate links under it.
- **The direct address does not open:** check that the app is running and that the host port is enabled under **Configuration → Network**. Try your Home Assistant IP address.
- **CookCLI reports an untrusted hostname or origin:** add the browser origin to `cors_origins` and restart the app.
- **Sign-in fails:** check username capitalization, save the configuration and restart the app. Check the app log for account creation or password update errors.
- **No recipes are visible:** check that the files have a `.cook` extension and are under `/share/cooklang/recipes`, rather than `/config`.
- **Git mode shows different recipes:** it serves the configured subdirectory under `/share/cooklang/git/repository`, not the old local recipe directory.
- **Git cannot connect or push:** verify the clone URL, branch, token or SSH key, verified SSH host keys when applicable, and write access to the branch. Consult the Git server logs; raw Git authentication output is deliberately omitted from app logs.
