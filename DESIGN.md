# Naukri Resume Automation Design

## Purpose

The application uploads a selected résumé to a Naukri profile as a safe one-shot operation. Windows 11 is the primary scheduled runtime; manual operation is supported on Windows, macOS, and Linux.

The application performs one run and exits. The operating-system scheduler owns timing.

## Architecture

```text
Windows Task Scheduler
        |
        v
  naukri-auto run --profile <name>
        |
        +--> validate config and resume
        +--> acquire single-run lock
        +--> open dedicated Playwright profile
        +--> verify or establish authentication
        +--> locate resume section
        +--> upload exact configured file
        +--> verify filename/update evidence
        +--> write sanitized result and artifacts
        +--> send optional notification
        +--> exit with stable status
```

The Python process will not remain running as a daemon and will not implement its own scheduling loop.

## Technology Choices

- Python 3.12 or newer.
- Playwright's synchronous Python API with an explicit Chrome, Edge, or managed Chromium channel.
- A `pyproject.toml` package with a `naukri-auto` console command.
- Typed per-profile TOML configuration stored in the user's application-data directory.
- `keyring` for credentials in Windows Credential Manager, macOS Keychain, or a supported Linux keyring.
- Windows Task Scheduler as the primary scheduler.
- `pytest` and Ruff for automated verification.

Playwright provides persistent browser contexts, actionable-element waiting, installed-browser channels, and failure traces. The default `chrome` channel uses the installed browser and does not require a separate browser download.

## Commands

### `naukri-auto profile create|list|show|edit|default`

Create and manage isolated profiles containing:

- profile name and Naukri username;
- managed résumé collection and active résumé;
- browser channel (`chrome`, `msedge`, or `chromium`);
- daily or weekly schedule and local timezone;
- headed or headless scheduled execution;
- optional notification endpoint/topic in the non-secret profile TOML;
- diagnostic artifact retention.

Passwords are collected only through hidden prompts and stored in the OS keyring. Configuration must never contain a password, session cookie, or browser token.

### `naukri-auto resume add|list|select|remove`

Copy résumés into a dedicated per-profile folder, retain multiple choices, and select exactly one active file without silently overwriting an existing import.

### `naukri-auto login --profile <name>`

Open the selected browser with a dedicated automation profile and let the user log in interactively. The profile is reused by scheduled runs. If CAPTCHA or MFA appears later, the run stops with `AUTH_REQUIRED` and asks the user to refresh this profile.

When logged out, the command may fill username/password from the OS credential store after the login form is detected. Submission, CAPTCHA, and MFA remain manual. When already authenticated, it confirms the persisted session without reading the credential.

### `naukri-auto doctor`

Perform side-effect-free checks:

- package and browser installation;
- configuration schema;
- resume existence, readability, type, non-empty content, and maximum size;
- application-data and profile permissions;
- scheduler availability;
- notification configuration.

It must not log in, select a file, upload a resume, or send a test notification unless separately requested.

### `naukri-auto run --dry-run`

Open the site, verify authentication, and find the resume section. Stop before selecting or uploading a file. The design must make it impossible for the dry-run path to invoke the upload operation.

### `naukri-auto run`

Perform one update attempt, verify the resulting UI, record the outcome, and exit. Merely calling Playwright's file-input method is not proof of success.

### `naukri-auto schedule install|show|run-now|remove`

Manage only the application's Windows scheduled task. Installation should display the exact schedule before applying it. The task should:

- run as the current non-administrator user, never `SYSTEM`;
- use absolute executable and working-directory paths;
- wake the computer from sleep when permitted;
- start when a scheduled run was missed;
- reject overlapping runs;
- stop after a maximum duration;
- expose last and next run status through `schedule show`.

## Local Data And Secrets

Use platform application-data directories rather than the repository:

```text
Windows configuration: %APPDATA%\NaukriAutomation\profiles\<name>\profile.toml
Windows mutable data:  %LOCALAPPDATA%\NaukriAutomation\profiles\<name>\
```

Each mutable profile directory may contain managed résumés, a dedicated browser profile, logs, run lock, result, screenshots, and Playwright traces. Authentication state is sensitive and must never be committed, printed, archived, or uploaded.

The repository must exclude:

- real resumes and generated PDFs;
- local configuration;
- credentials and environment files;
- browser profiles, cookies, or storage state;
- screenshots, traces, and logs;
- virtual environments, caches, build output, and `.DS_Store`.

The application uploads the exact managed résumé and never mutates its contents. If Naukri rejects identical content, the run fails explicitly rather than modifying the document.

## Workflow Boundaries

Keep Naukri-specific UI behavior in one module. Prefer locators based on role, label, and visible text, with narrow fallbacks. Avoid hard-coded sleeps.

The workflow must:

1. validate all local inputs before opening the browser;
2. acquire a lock before external work;
3. distinguish authenticated, logged-out, CAPTCHA/MFA, and unexpected-page states;
4. stop safely when the site contract is unknown;
5. upload only after all preconditions pass;
6. verify filename and last-updated evidence after upload;
7. close the browser and release the lock in every outcome.

## Results, Retries, And Diagnostics

Stable result categories:

- `SUCCESS`
- `DRY_RUN_SUCCESS`
- `CONFIG_ERROR`
- `AUTH_REQUIRED`
- `SITE_CHANGED`
- `UPLOAD_FAILED`
- `NETWORK_ERROR`
- `ALREADY_RUNNING`
- `DEPENDENCY_ERROR`
- `INTERNAL_ERROR`

Runs are not retried automatically. This prevents a duplicate upload when an earlier attempt has an unknown outcome.

On failure, retain:

- a sanitized structured log;
- a screenshot;
- a Playwright trace when enabled;
- the result category, timestamp, host, and application version.

Apply bounded retention. Never retain credentials, cookies, full HTML/body dumps, or resume contents in logs or notifications.

Notifications are optional and best-effort. Notification failure does not change a successful upload into an upload failure.

## Repository Layout

```text
Automation/
  pyproject.toml
  README.md
  DESIGN.md
  LICENSE
  .gitignore
  config.example.toml
  src/naukri_automation/
    __init__.py
    cli.py
    config.py
    credentials.py
    paths.py
    profile_cli.py
    profile_store.py
    result.py
    run_lock.py
    workflow.py
    browser_session.py
    naukri_site.py
    notifications.py
    scheduling/
      __init__.py
      windows.py
  tests/
    test_config.py
    test_browser_session.py
    test_cli_login.py
    test_naukri_site.py
    test_profiles.py
    test_workflow.py
    test_notifications.py
    test_windows_schedule.py
```

Scheduler management is Windows-only; the core commands remain cross-platform.

## Deployment Model

Use the Windows 11 system and Task Scheduler first. It keeps authentication local, reuses a dedicated browser profile, and can wake a sleeping computer. It cannot operate while the machine is fully powered off.

An always-on host can be added later if execution must be independent of the personal computer. Hosted CI runners are not a supported runtime because they require exporting the browser session and résumé outside the user's machine.

## Official References

- [Playwright Python library](https://playwright.dev/python/docs/library)
- [Playwright auto-waiting](https://playwright.dev/python/docs/actionability)
- [Playwright authentication state](https://playwright.dev/python/docs/auth)
- [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [Microsoft `schtasks`](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks)
- [Microsoft Task Scheduler `WakeToRun`](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-waketorun)
- [Python keyring](https://keyring.readthedocs.io/en/stable/)
