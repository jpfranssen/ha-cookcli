# Changelog

## 0.3.0

- Add optional two-way Git synchronization with a configurable branch, recipe subdirectory, interval and commit identity.
- Support SSH write keys and pinned host keys for self-hosted Git servers.
- Accept inline SSH keys/host keys and masked HTTPS tokens in app configuration, including Home Assistant secret references; scope HTTPS credentials to the configured repository.
- Keep the Git backend separate from the server coordinator for future phone synchronization.
- Commit local edits before merging, merge in an isolated worktree and retain both commits on conflict without serving conflict markers.
- Preserve local commits when offline or when pushes are rejected; retry without force-pushing.
- Add JSON sync status, setup and recovery documentation, English/Dutch configuration labels, and local Git integration tests in CI.
- Briefly stop and restart CookCLI for local Git changes to coordinate web writes; keep network operations outside that pause.
- Test the packaged Git backend and a complete authenticated web-edit/push/restart/pull flow against a private local HTTPS Git server inside the image.

## 0.2.3

- Match usernames in the first column of CookCLI's user list, which also includes roles.
- Stop startup if listing existing accounts fails instead of trying to create them again.
- Add a container regression test for similar usernames, restarts and password changes.

## 0.2.2

- Add a configurable trusted web origin for hostname access while keeping CSRF and DNS rebinding checks enabled.
- Replace ambiguous shell conditionals to pass ShellCheck and report state-file move failures.
- Add an MIT license.
- Add CI for app linting, shell checks, amd64 Docker builds and basic image checks.
- Remove explicit default startup options to satisfy the app linter.
- Use English for the README, repository metadata and startup messages.
- Add English configuration labels while keeping the Dutch translation.
- Add a user guide for the Home Assistant Documentation tab.
- Add contributor and release instructions.

## 0.2.1

- Package CookCLI 0.39.0 for Home Assistant on amd64.
- Store recipes in `/share/cooklang/recipes` and configuration under `/data`.
- Create accounts and update changed passwords from app options at startup.
- Match complete usernames when checking existing accounts.
- Add repository metadata and installation documentation.
