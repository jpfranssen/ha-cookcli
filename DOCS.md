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

The recipe directory is currently fixed. There is no option to select another directory, and the app does not automatically synchronize recipes with Git.

## Storage and backups

| Data | Path inside the CookCLI app |
| --- | --- |
| Recipes | `/share/cooklang/recipes` |
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
