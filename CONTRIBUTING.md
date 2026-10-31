# Contributing

This app is experimental. Bug reports should include your app version, CPU architecture, reproduction steps and relevant logs. Remove passwords and other personal information before sharing configuration or logs.

Use English for documentation, issues, pull requests and default app messages. Localized configuration labels belong in `translations/`; keep the English and Dutch keys aligned.

## Repository layout

This repository contains a single app at its root. `repository.yaml` describes the app repository; `config.yaml` describes CookCLI. The app is built from the root Dockerfile. Keep the repository URL and `slug` stable so existing installations retain their identity.

- `README.md`: overview and installation.
- `DOCS.md`: configuration and usage, also shown in Home Assistant.
- `CHANGELOG.md`: changes by app version.
- `run.sh`: persistent storage setup, account configuration and server startup.
- `sync_service.py`: server lifecycle, edit settling and sync coordination.
- `git_sync.py`: Git backend, private merge worktree and sync status.
- `git_credentials.py`: repository-scoped HTTPS credential helper.
- `translations/`: localized configuration labels.

## Validate changes

Before submitting a change:

1. Run `sh -n run.sh` and `git diff --check`.
   Run `python3 -m unittest discover -s tests -p test_git_sync.py -v` for real local Git tests (no network or Docker required).
2. Build the image on a Linux Docker host: `docker build -t ha-cookcli:test .`.
3. Test installation in Home Assistant OS on amd64. Check startup, account creation, password changes, recipe editing and persistence after a restart.
4. Confirm that `jan` and `jansen` are treated as separate accounts and that removing a configured user does not silently delete their account.

A successful Docker build does not replace a Home Assistant installation test. After building `ha-cookcli:ci`, run `python3 tests/test_startup.py` to test account creation with a similar existing username, restarts and password changes against the real image.

Run the packaged Git tests and the complete web/API synchronization test inside disposable containers (PowerShell: substitute an absolute tests path for `$PWD/tests`):

```sh
docker run --rm -v "$PWD/tests:/tests:ro" -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 --entrypoint python3 ha-cookcli:ci -m unittest discover -s /tests -p test_git_sync.py -v
docker run --rm -v "$PWD/tests:/tests:ro" -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 --entrypoint python3 ha-cookcli:ci /tests/container_git_sync.py -v
```

The latter starts a private HTTPS Git server inside the disposable container, creates a temporary CA certificate and synthetic token, signs in to CookCLI, edits a recipe over HTTP, checks the pushed commit, restarts the app and verifies a remote update. It never connects to GitHub or uses real credentials. Browser editor behavior and an actual Home Assistant installation still require manual validation.

## Continuous integration

The [CI workflow](.github/workflows/ci.yaml) runs on pushes and pull requests, and can also be started manually from GitHub's Actions tab. It uses two jobs:

- **Lint:** check shell syntax with `sh`, analyze `run.sh` with ShellCheck, and validate the app with the Home Assistant app linter used by the official example repository.
- The lint job also runs Git synchronization integration tests with temporary local repositories.
- **Build:** build the Linux amd64 Docker image, check the packaged script's syntax, run `cook --version`, and test persistent user setup across container restarts.

The workflow builds a test image on a temporary GitHub runner. It does not publish images to a registry or deploy updates to Home Assistant. No registry credentials are needed. Results and failure logs appear in the repository's Actions tab and on pull requests. Requiring these checks before merging is a separate GitHub branch protection setting.

## Release an update

The Home Assistant app version and the upstream CookCLI version are independent. For example, an app-only fix can become `0.2.2` while keeping CookCLI at `0.39.0`.

1. Test the change.
2. Increase `version` in `config.yaml` and the default `BUILD_VERSION` in the Dockerfile to the same value.
3. Update the version in the README and move the Unreleased changelog entries under the new version.
4. Commit and push to `main`.
5. Check for updates in Home Assistant and test the upgrade from the previous app version.
6. Optionally add a matching Git tag and GitHub release with the changelog.

Home Assistant builds images on the user's device because `config.yaml` has no `image` entry. A GitHub release alone does not update the app version in the store. See the [Home Assistant app configuration reference](https://contributors.home-assistant.io/apps/reference/configuration/#image).

## Next steps toward the official template

Compared with the [official example repository](https://github.com/home-assistant/apps-example), the main remaining work is:

- Test and publish prebuilt images before introducing an `image` entry.
- Verify upstream image support and runtime behavior on ARM before adding `aarch64`.
- Develop and test an app-specific AppArmor profile using actual runtime requirements.

Ingress would improve access from Home Assistant, but requires testing CookCLI's paths, origins and authentication. It is not enabled by the official example's app configuration either.

## Extending synchronization

`GitBackend` owns repository-specific preparation, sync cycles and status. `sync_service.py` owns the CookCLI process and provides the `paused()` boundary used for local writes. Fetching and pushing must happen outside that boundary. Always restart the server after a failed local operation, and never apply an unresolved merge to its recipe directory.

Future phone synchronization is a separate transport, not an alternative to Git history. Add it through the coordinator so file writes cannot race with checkout updates. Do not point an independent sync daemon at the live checkout until it can participate in that boundary. Keep credentials, repository metadata and status outside the served recipe subdirectory. The first version uses one Git backend and one writer; it deliberately has no dynamic plugin loader.
