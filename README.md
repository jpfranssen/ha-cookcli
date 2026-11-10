# CookCLI for Home Assistant

[![CI](https://github.com/jpfranssen/ha-cookcli/actions/workflows/ci.yaml/badge.svg)](https://github.com/jpfranssen/ha-cookcli/actions/workflows/ci.yaml)

Browse and manage your [Cooklang](https://cooklang.org/) recipes from Home Assistant. CookCLI opens inside Home Assistant through Ingress, with an optional sidebar entry. Keep recipes as plain `.cook` files in Home Assistant's shared folder or synchronize them with a Git repository.

**Experimental** — App version **0.4.4** uses **CookCLI 0.41.1** and supports **amd64 (Intel/AMD x86-64)**.

## Install

You need Home Assistant OS with the app store. Home Assistant Container does not include the app store.

[![Add this repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fjpfranssen%2Fha-cookcli)

Or add it manually:

1. Go to **Settings → Apps → Install app**. Older versions use **Add-ons → Add-on Store**.
2. Open the three-dot menu and select **Repositories**.
3. Add `https://github.com/jpfranssen/ha-cookcli`.
4. Find **CookCLI** and select **Install**. Home Assistant builds the image on your device, so the first installation may take a while.
5. Before starting the app, add at least one user under **Configuration** and save:

   ```yaml
   users:
     - username: cook
       password: "replace-with-your-own-password"
   ```

6. Start the app and check the **Log** tab.
7. Select **Open Web UI** on the CookCLI app page. Enable **Show in sidebar** to add the **Recepten** entry with a chef-hat icon.

The direct HTTP listener is published on port `9080` by default. For a browser origin that CookCLI rejects, add the exact URL origin to the `cors_origins` list, save and restart. When upgrading from `0.3.0` or earlier, move any existing `cors_origin` value into that list. See [web access and configuration examples](DOCS.md#open-the-web-interface).

Home Assistant controls access to Ingress. CookCLI accounts separately control who can make changes in the recipe UI. On a fresh installation without users, anyone who can reach CookCLI can make changes. Once an account exists, visitors can browse recipes and must sign in to make changes.

See Home Assistant's [third-party repository installation guide](https://www.home-assistant.io/common-tasks/os#installing-a-third-party-app-repository) for more information.

## Add recipes

The app creates `/share/cooklang/recipes` on first start. Copy your `.cook` files into this folder, optionally organized in subfolders, or manage recipes through the CookCLI web interface.

With the **Samba share** app, Windows users can access the folder at:

```text
\\<home-assistant-ip>\share\cooklang\recipes
```

## Git synchronization

Optionally synchronize a recipe repository with your own Git server or GitHub. The app commits web edits, fetches and merges remote changes, and pushes without rewriting history. Configure `sync.git` in Home Assistant; it is disabled by default. Enter an HTTPS access token or SSH private key directly in the app configuration, with secret references supported. SSH file inputs remain available. See the [setup and conflict recovery guide](DOCS.md#git-synchronization).

In Git mode CookCLI serves `/share/cooklang/git/repository/<recipes_subdirectory>`. Existing files in `/share/cooklang/recipes` are never overwritten. Conflicts leave the local recipes usable and preserve both commits. The web server briefly restarts when committing or integrating changes; network operations run while it is available.

## Documentation

Read the [user guide](DOCS.md) for account configuration, a sample recipe, storage, backups and troubleshooting. It is also available from the app's **Documentation** tab in Home Assistant.

- [Changelog](CHANGELOG.md)
- [Contributing and releases](CONTRIBUTING.md)
- [Report a bug or request a feature](https://github.com/jpfranssen/ha-cookcli/issues)
- [Upstream CookCLI](https://github.com/cooklang/cookcli)

## Current limitations

- Only `amd64` is supported.
- Local mode uses `/share/cooklang/recipes`; Git mode uses a subdirectory of its own checkout.
- Removing a user from the app configuration does not delete their CookCLI account.
- Git conflicts require manual resolution; there is no conflict editor or Home Assistant status entity yet.
- Git sync supports SSH keys and HTTPS tokens; encrypted SSH keys and phone synchronization are not implemented.
- Images are built on installation; prebuilt images are not published yet.

## License

This repository is licensed under the [MIT License](LICENSE). CookCLI and other bundled dependencies retain their own licenses.
