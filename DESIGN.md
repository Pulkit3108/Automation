# Naukri Resume Automation Design

## Objective

Build a maintainable Python application that uploads a configured resume to the user's Naukri profile at a user-selected time. Windows 11 is the primary deployment target. Manual runs and development should remain compatible with macOS and Linux.

The application performs one run and exits. The operating-system scheduler owns timing.

## Recommended Architecture

```text
Windows Task Scheduler
        |
        v
  naukri-auto run
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

- Python 3.12 as the initial supported runtime.
- Playwright's synchronous Python API with managed Chromium.
- A `pyproject.toml` package with a `naukri-auto` console command.
- Typed TOML configuration stored in the user's application-data directory.
- `keyring` for optional credentials in Windows Credential Locker or macOS Keychain.
- Windows Task Scheduler as the primary scheduler.
- `pytest`, Ruff, and type checking for automated verification.

Playwright replaces Selenium because it manages supported browser binaries, auto-waits for actionable elements, supports persistent contexts, and produces traces and screenshots useful for diagnosing site changes.

## Commands

### `naukri-auto configure`

Interactively configure:

- absolute resume path;
- daily or weekly schedule and local timezone;
- headed or headless scheduled execution;
- optional notification endpoint/topic;
- diagnostic artifact retention.

Configuration must never contain a password, session cookie, or browser token.

### `naukri-auto login --headed`

Open a dedicated Chromium profile and let the user log in interactively. The profile is reused by scheduled runs. If CAPTCHA or MFA appears later, the run stops with `AUTH_REQUIRED` and asks the user to refresh this profile.

An optional automatic-login fallback may read username/password from the OS credential store. It will never bypass CAPTCHA or MFA.

### `naukri-auto doctor`

Perform side-effect-free checks:

- package and browser installation;
- configuration schema;
- resume existence, readability, type, non-empty content, and maximum size;
- application-data and profile permissions;
- scheduled-task visibility;
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
- retry a bounded number of times after transient failure;
- reject overlapping runs;
- stop after a maximum duration;
- expose last and next run status through `schedule show`.

## Local Data And Secrets

Use platform application-data directories rather than the repository:

```text
Windows configuration: %APPDATA%\NaukriAutomation\config.toml
Windows mutable data:  %LOCALAPPDATA%\NaukriAutomation\
```

The mutable directory may contain the dedicated browser profile, logs, run lock, screenshots, and Playwright traces. Authentication state is sensitive and must never be committed, printed, archived, or uploaded.

The repository must exclude:

- real resumes and generated PDFs;
- local configuration;
- credentials and environment files;
- browser profiles, cookies, or storage state;
- screenshots, traces, and logs;
- virtual environments, caches, build output, and `.DS_Store`.

The old hidden-random-text PDF mutation will be removed. The exact user-provided resume is uploaded. If Naukri rejects identical content, that behavior will be investigated explicitly instead of silently changing document content.

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
- `CONFIG_ERROR`
- `AUTH_REQUIRED`
- `SITE_CHANGED`
- `UPLOAD_FAILED`
- `NETWORK_ERROR`
- `ALREADY_RUNNING`

Retry only transient navigation and network failures with bounded backoff. Do not retry authentication failures, invalid configuration, selector-contract failures, or an upload with an unknown outcome.

On failure, retain:

- a sanitized structured log;
- a screenshot;
- a Playwright trace when enabled;
- the result category, timestamp, host, and application version.

Apply bounded retention. Never retain credentials, cookies, full HTML/body dumps, or resume contents in logs or notifications.

Notifications are optional and best-effort. Notification failure does not change a successful upload into an upload failure.

## Proposed Repository Layout

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
    paths.py
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
    fixtures/
    test_config.py
    test_workflow.py
    test_notifications.py
    test_windows_schedule.py
  scripts/
    install-windows.ps1
```

Do not add macOS/Linux scheduler installers until the Windows path is proven. The core commands remain cross-platform without them.

## Delivery Plan

### Phase 1: Safe foundation

- package layout and CLI;
- typed configuration and platform paths;
- result model, logging, run lock, and retention;
- side-effect-safe tests and secret scanning;
- `configure` and `doctor`.

Acceptance: clean install, tests pass without network access, and no sensitive/runtime file is tracked.

### Phase 2: Browser workflow

- Playwright installation and profile bootstrap;
- authentication-state handling;
- dry-run and upload workflows;
- centralized locators and post-upload verification;
- screenshots/traces and fixture-backed tests.

Acceptance: tests prove dry-run cannot upload; a headed local dry run reaches the expected resume section without modifying the profile.

### Phase 3: Windows scheduling

- install, inspect, run-now, and remove the scheduled task;
- wake, missed-run, bounded retry, overlap, and timeout settings;
- Windows installation and troubleshooting documentation.

Acceptance: schedule configuration round-trips on Windows 11 and reports the next/last run accurately.

### Phase 4: Controlled live canary

- interactive login/profile refresh;
- one explicitly authorized upload;
- verify the expected filename and update evidence;
- confirm notification and diagnostic behavior.

Acceptance: Naukri and the local result both confirm success, with no secret leakage.

## Deployment Decision

Use the Windows 11 system and Task Scheduler first. It keeps authentication local, reuses a dedicated browser profile, and can wake a sleeping computer. It cannot operate while the machine is fully powered off.

An always-on VM can be added later if independence from the personal machine becomes mandatory. GitHub-hosted Actions is not the preferred runtime because scheduled jobs may be delayed, authentication state and the resume become runner secrets, and cloud-run browser behavior may differ from the user's normal session.

## Official References

- [Playwright Python library](https://playwright.dev/python/docs/library)
- [Playwright auto-waiting](https://playwright.dev/python/docs/actionability)
- [Playwright authentication state](https://playwright.dev/python/docs/auth)
- [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [Microsoft `schtasks`](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks)
- [Microsoft Task Scheduler `WakeToRun`](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-waketorun)
- [Python keyring](https://keyring.readthedocs.io/en/stable/)
- [GitHub Actions scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
