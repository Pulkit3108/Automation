# Repository Agent Instructions

## Scope

- `src/naukri_automation/` is the supported implementation. Do not recreate root-level ad hoc automation scripts.
- Keep manual profile, credential, résumé, login, doctor, and run commands compatible with Windows, macOS, and Linux.
- Windows Task Scheduler is the only scheduler integration. The application must remain a one-shot command, not a resident daemon.

## Safety Boundaries

- Treat every non-dry `naukri-auto run` as an external write to the user's Naukri profile. Run it only with explicit authorization for that upload.
- Run `login` only when the user requests authentication setup or refresh. CAPTCHA, MFA, and final login submission remain manual.
- `run --dry-run` must stop before file selection or upload. Preserve an automated regression test for this boundary.
- Require explicit approval before installing, triggering, replacing, or removing a Windows scheduled task, sending a real notification, deleting a profile or credential, or removing a managed résumé.
- Never retry an upload automatically when its outcome is unknown. Require manual inspection before another attempt.
- Do not attempt to bypass CAPTCHA, MFA, anti-bot controls, or account restrictions.

## Secrets And Local Data

- Passwords belong only in the operating-system keyring and must be collected through hidden prompts. Never accept or store them in source, TOML, `.env`, command arguments, logs, notifications, tests, or documentation.
- Treat browser profiles, cookies, résumés, screenshots, traces, logs, results, and generated task files as private local data. Keep them outside Git.
- Keep profile configuration and mutable state in the platform application-data directories defined by `paths.py`; do not add repository-local runtime configuration.
- Examples and fixtures must contain synthetic identities, paths, topics, and documents only.

## Architecture Invariants

- Keep command parsing and orchestration in `cli.py` and `profile_cli.py`; keep Naukri-specific page behavior and selectors in `naukri_site.py`.
- Use a dedicated persistent browser directory per profile and a separate lock, result, log/artifact area, keyring entry, and Windows task name per profile.
- Validate configuration and the selected managed résumé before opening the browser.
- Report upload success only after post-upload UI evidence is observed. Selecting a file is not proof of success.
- Preserve stable outcomes and exit codes in `result.py`; notifications remain best-effort and must not change a successful upload into a failure.
- Keep Windows tasks least-privileged, tied to the current interactive user, overlap-safe, wake-capable when configured, and time-bounded. Never run them as `SYSTEM`.

## Cross-Platform Behavior

- Support Python 3.12 or newer.
- Use installed Google Chrome by default. Support installed Edge and Playwright-managed Chromium only when explicitly configured.
- Do not require a Playwright browser download for the default Chrome path.
- Fail safely when a secure OS-keyring backend is unavailable; never fall back to plaintext credential storage.
- Guard Windows-only scheduler code so all other commands remain usable on macOS and Linux.

## Verification

- Keep default automated tests isolated from live browsers, Naukri, notifications, OS keyrings, and Task Scheduler by using test doubles.
- For normal source changes, run:

  ```text
  ruff check .
  pytest
  python -m pip check
  ```

- Add or update focused tests for changed behavior, especially authentication classification, dry-run isolation, upload verification, profile separation, configuration validation, and task XML generation.
- Do not treat mocks as proof of live Naukri or Windows behavior. Record environment-specific validation separately from product documentation.

## Documentation

- Keep `README.md` user-facing: features, installation, setup, commands, troubleshooting, and security.
- Keep `DESIGN.md` limited to current architecture, invariants, and durable design decisions.
- Do not add task progress, milestone history, migration history, completed/pending work lists, or temporary validation notes to repository documentation.
- Keep command examples synchronized with `naukri-auto --help` and use synthetic values.

## Git And Change Hygiene

- Preserve unrelated work and inspect the worktree before editing.
- Do not create a branch, commit, push, open a pull request, or merge without explicit user authorization for that action.
- Stage only files belonging to the requested change.
- Do not commit application data, virtual environments, caches, generated artifacts, real résumés, or credentials.
