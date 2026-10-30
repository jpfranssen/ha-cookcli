# Contributing

This app is experimental. Bug reports should include your app version, CPU architecture, reproduction steps and relevant logs. Remove passwords and other personal information before sharing configuration or logs.

Use English for documentation, issues, pull requests and default app messages. Localized configuration labels belong in `translations/`; keep the English and Dutch keys aligned.

## Repository layout

This repository contains a single app at its root. `repository.yaml` describes the app repository; `config.yaml` describes CookCLI. The app is built from the root Dockerfile. Keep the repository URL and `slug` stable so existing installations retain their identity.

- `README.md`: overview and installation.
- `DOCS.md`: configuration and usage, also shown in Home Assistant.
- `CHANGELOG.md`: changes by app version.
- `run.sh`: persistent storage setup, account configuration and server startup.
- `translations/`: localized configuration labels.

## Validate changes

Before submitting a change:

1. Run `sh -n run.sh` and `git diff --check`.
2. Build the image on a Linux Docker host: `docker build -t ha-cookcli:test .`.
3. Test installation in Home Assistant OS on amd64. Check startup, account creation, password changes, recipe editing and persistence after a restart.
4. Confirm that `jan` and `jansen` are treated as separate accounts and that removing a configured user does not silently delete their account.

A successful Docker build does not replace a Home Assistant installation test. Full account and recipe runtime tests have not been added yet.

## Continuous integration

The [CI workflow](.github/workflows/ci.yaml) runs on pushes and pull requests, and can also be started manually from GitHub's Actions tab. It uses two jobs:

- **Lint:** check shell syntax with `sh`, analyze `run.sh` with ShellCheck, and validate the app with the Home Assistant app linter used by the official example repository.
- **Build:** build the Linux amd64 Docker image, check the packaged script's syntax, and run `cook --version` to check that the binary starts.

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
