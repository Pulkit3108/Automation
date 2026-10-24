# Naukri Resume Automation Design

## Purpose

The application performs a verified one-shot résumé update against one configured Naukri profile.
Manual and scheduled entry points use the same workflow. Native operating-system schedulers own
timing; the Python application never remains resident as a scheduling daemon.

User installation and commands belong in [`setup/`](setup/README.md). Repository-maintenance rules
belong in [`AGENTS.md`](AGENTS.md). This document owns architecture and durable design decisions.

## Core Principles

- Validate configuration and the managed résumé before opening a browser.
- Keep credentials exclusively in the OS keyring.
- Reuse private browser session data without keeping a browser process alive.
- Treat CAPTCHA and MFA as manual challenges and never bypass them.
- Stop before upload during a dry run.
- Report success only after new post-upload UI evidence appears.
- Never retry an upload whose outcome is unknown.
- Use native, least-privileged, persistent schedulers.
- Prevent overlapping work at both scheduler and application layers.
- Keep logs and failure artifacts bounded and outside Git.

## System Flow

```text
Manual CLI or native scheduler
        |
        v
resolve named profile and platform paths
        |
        v
validate configuration and managed résumé
        |
        v
acquire per-profile process lock
        |
        v
launch one persistent-data browser context
        |
        +--> classify authentication
        +--> inspect résumé section
        +--> stop here for dry run
        +--> select exact managed résumé
        +--> wait for any valid post-upload evidence
        |
        v
write structured result and rotating log
        |
        +--> retain bounded failure evidence when needed
        +--> attempt optional notification
        |
        v
close browser context and release lock
```

## Component Boundaries

| Component | Responsibility |
| --- | --- |
| `cli.py` | Command parsing, orchestration, readiness checks, and user-facing outcomes |
| `profile_cli.py` | Profile, credential, résumé, and cleanup lifecycle |
| `schedule_cli.py` | Schedule-rule commands and native scheduler orchestration |
| `profile_store.py` | Managed profile configuration and résumé storage |
| `config.py` | Typed configuration, schedule rules, validation, and TOML rendering |
| `credentials.py` | OS-keyring access without plaintext fallback |
| `browser_session.py` | Playwright lifecycle, persistent browser data, tracing, and cleanup |
| `naukri_site.py` | Naukri URLs, selectors, authentication classification, and upload evidence |
| `workflow.py` | Locked dry-run/upload state machine and stable results |
| `run_lock.py` | Per-profile mutual exclusion and dead-owner recovery |
| `result.py` | Stable outcomes, exit codes, and atomic result persistence |
| `notifications.py` | Optional best-effort sanitized notification delivery |
| `scheduling/base.py` | Shared native scheduler contract and errors |
| `scheduling/` platform modules | Windows, macOS, and Linux job generation and management |

Naukri-specific page behavior stays in `naukri_site.py`; platform scheduler behavior stays in the
matching scheduler module. Core profile and workflow code remains platform-neutral.

## Profile And Local Data Model

Each named profile owns:

- username or email;
- one selected managed résumé plus optional inactive managed copies;
- browser channel and headed/headless preference;
- timeout, retention, size, notification, and schedule settings;
- an OS-keyring entry keyed by profile name;
- a dedicated browser-data directory, log, result, artifacts, and lock;
- one native scheduler job.

Configuration lives in the platform configuration directory. Mutable and sensitive state lives in
the platform data directory. The repository contains neither runtime configuration nor user data.

Profile removal is a confirmed lifecycle operation. It verifies/removes the scheduler job, removes
the keyring credential, then deletes managed configuration and mutable state. It never deletes the
repository or the original résumé used for import.

## Authentication State Machine

The login flow classifies the page as:

- authenticated;
- login required;
- invalid credentials;
- visible CAPTCHA/MFA challenge;
- unknown contract.

A recognized form may be filled and submitted from the keyring. Hidden CAPTCHA markup does not
count as an active challenge. Invalid credentials close cleanly with recovery guidance. Visible
CAPTCHA or MFA waits for manual completion. Unknown pages stop after a bounded timeout and save a
private screenshot and Playwright trace.

The browser profile retains cookies and authentication state across runs. Credential values are
never written to configuration, arguments, logs, results, notifications, screenshots by the
application, or test fixtures.

## Upload Correctness

The dry-run path cannot invoke file selection. A real upload selects exactly the configured managed
file and waits once for any of these new post-upload signals:

- a success message;
- a filename that was not visible before selection;
- changed résumé update evidence.

An already-visible filename is not proof of a new upload. Verification timeout produces
`UPLOAD_FAILED`, retains diagnostics, and explicitly forbids automatic retry.

## Scheduling Architecture

Schedules contain independent rules. Each rule has one or more local `HH:MM` times and either all
days or selected weekdays. Overlapping day/time occurrences are rejected. The total is bounded by
the Windows maximum of 48 native triggers.

| Platform | Implementation | Persistence model |
| --- | --- | --- |
| Windows | Task Scheduler XML | Current interactive user task |
| macOS | `~/Library/LaunchAgents` plist | Per-user GUI LaunchAgent |
| Linux | `~/.config/systemd/user` service and timer | Enabled user timer |

Windows task XML includes the current user, interactive-token logon, least privilege, absolute
executable and working-directory paths, `IgnoreNew`, battery-safe behavior, optional wake, and a
30-minute execution limit. Import XML is written as UTF-16 bytes with a matching declaration and
BOM.

Installed jobs survive terminal closure and reboot. The user session must be signed in so the
keyring and dedicated browser profile are available. Screen lock and display sleep do not prevent a
headless run. A powered-off machine cannot execute work.

## Concurrency And Resource Lifecycle

Two independent controls prevent overlap:

1. the native scheduler refuses or ignores a second instance for the same job;
2. the per-profile lock protects manual and scheduled entry points.

A live same-host owner keeps the lock. A dead same-host owner is reclaimed immediately. Unreadable
or foreign lock metadata expires after the configured stale interval.

Every run starts one browser process and persistent-data context. The process and context close in
the context-manager cleanup path on success or failure. Cookies and session data persist; browser
processes do not. Successful traces are stopped and discarded. Failure screenshots and traces are
retained only under the profile artifacts directory and are pruned by retention policy.

Application logs rotate at 1 MB with five backups. Result writes use a temporary file and atomic
replacement. Optional notification failure never changes a verified upload into a failure.

## Results And Diagnostics

Stable outcomes are:

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

Each result contains a UTC timestamp, sanitized message, optional private artifact path, and stable
exit code. Logs record outcome categories and exception types without credentials, cookies, résumé
contents, or full page bodies.

## Repository Layout

```text
Automation/
  AGENTS.md
  DESIGN.md
  README.md
  config.example.toml
  pyproject.toml
  setup/
    README.md
    windows.md
    macos-linux.md
  src/naukri_automation/
    browser_session.py
    cli.py
    config.py
    credentials.py
    naukri_site.py
    notifications.py
    paths.py
    profile_cli.py
    profile_store.py
    schedule_cli.py
    result.py
    run_lock.py
    workflow.py
    scheduling/
      base.py
      windows.py
      macos.py
      linux.py
  tests/
    test_schedule_cli.py
```

## Official References

- [Playwright Python](https://playwright.dev/python/docs/library)
- [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [Microsoft Task Scheduler](https://learn.microsoft.com/en-us/windows/win32/api/_taskschd/)
- [Apple timed jobs with launchd](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html)
- [systemd timers](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)
- [Python keyring](https://keyring.readthedocs.io/en/stable/)
