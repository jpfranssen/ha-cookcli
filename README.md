# CookCLI for Home Assistant

[![CI](https://github.com/jpfranssen/ha-cookcli/actions/workflows/ci.yaml/badge.svg)](https://github.com/jpfranssen/ha-cookcli/actions/workflows/ci.yaml)

Browse and manage your [Cooklang](https://cooklang.org/) recipes from Home Assistant. CookCLI opens inside Home Assistant through Ingress, with an optional sidebar entry. Keep recipes as plain `.cook` files in Home Assistant's shared folder or synchronize them with a Git repository.

**Experimental** — App version **0.4.5** uses **CookCLI 0.41.1** and supports **amd64 (Intel/AMD x86-64)**.

## Start here

You need Home Assistant OS with the app store. Home Assistant Container does not include the app store.

[![Add this repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fjpfranssen%2Fha-cookcli)

1. **Install CookCLI** from the app store. To add the repository manually, go to **Settings → Apps → Install app → ⋮ → Repositories** and enter `https://github.com/jpfranssen/ha-cookcli`. Home Assistant builds the image on your device.
2. **Add a CookCLI user** under **Configuration → Users** and save. Home Assistant controls access to the page. The CookCLI account controls editing. See [account setup](DOCS.md#configure-users).
3. **Start** the app and select **Open Web UI**. Optionally turn on **Show in sidebar** to add the **Recepten** shortcut.
4. **Add your first recipe.** Sign in to CookCLI to create one in the UI, or copy existing `.cook` files to `/share/cooklang/recipes`. See [an example recipe](DOCS.md#example-recipe).

For GitHub or a self-hosted Git server, follow the [Git synchronization guide](docs/git-sync.md). To connect an API client such as the CookCLI integration, see [direct access](DOCS.md#direct-access-for-api-clients).

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
