# Naukri Resume Automation

A Windows-first, cross-platform Python application for updating a configured resume on Naukri at a chosen time.

The application performs one run and exits. Windows Task Scheduler owns the schedule, so no Python process needs to remain running all day. Manual runs are supported on Windows, macOS, and Linux.

> [!IMPORTANT]
> A real upload changes the remote Naukri profile. On every new machine and account, run `doctor`, interactive login, and a headed dry run before the first upload.

## Features

- named profiles with separate credentials, résumés, browser sessions, and schedules;
- secure password storage through the operating-system keyring;
- managed résumé import, selection, and removal;
- interactive login with persistent browser sessions;
- side-effect-free readiness checks and headed dry runs;
- one-shot uploads with post-upload verification, structured results, and failure diagnostics;
- optional ntfy-compatible notifications;
- Windows Task Scheduler integration for daily or weekly execution.

See [DESIGN.md](DESIGN.md) for architecture and safety boundaries.

## Requirements

- Python 3.12 or newer;
- Google Chrome by default, or Microsoft Edge / Playwright-managed Chromium when configured;
- Windows 11 for automatic scheduling; manual commands work on Windows, macOS, and Linux;
- internet access when installing dependencies and running Naukri automation.

Linux credential storage requires a working Secret Service-compatible keyring. If no secure backend is available, profile creation fails instead of storing a password insecurely.

## Windows Installation

Run in PowerShell from this repository:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Keep this virtual environment after installing the scheduled task. The task records the absolute Python interpreter path used during installation.

## macOS Or Linux Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Browser Selection

The default `browser_channel = "chrome"` uses the machine's installed Google Chrome, so no browser copy or Playwright browser download is required. Set it to `"msedge"` to use installed Microsoft Edge. Set it to `"chromium"` only if you prefer Playwright's managed browser, then install that version-specific payload with:

```text
python -m playwright install chromium
```

## First-Time Setup

### 1. Create A Profile

```text
naukri-auto profile create personal --username you@example.com --resume C:\Users\you\Documents\resume.pdf
```

The password is requested through a hidden prompt and stored in Windows Credential Manager, macOS Keychain, or the available Linux keyring. It is never stored in TOML or accepted as a command-line argument. The résumé is copied into the profile's managed local folder, so the source file can later be moved or removed.

Default locations:

| Platform | Configuration | Mutable data |
| --- | --- | --- |
| Windows | `%APPDATA%\NaukriAutomation\profiles\<name>\profile.toml` | `%LOCALAPPDATA%\NaukriAutomation\profiles\<name>\` |
| macOS | `~/Library/Application Support/NaukriAutomation/profiles/<name>/profile.toml` | same application-support directory |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/NaukriAutomation/profiles/<name>/profile.toml` | `${XDG_STATE_HOME:-~/.local/state}/NaukriAutomation/profiles/<name>/` |

The first profile becomes the default. With multiple profiles, use `--profile <name>` or select a default with `naukri-auto profile default <name>`. The complete management command list is in [Command Reference](#command-reference).

Every profile has separate configuration, managed résumés, browser cookies, logs, artifacts, lock, result, keyring entry, and Windows task name. Two local profiles using the same Naukri username still modify the same remote Naukri account, so do not schedule them at overlapping times.

### 2. Check Local Readiness

```text
naukri-auto doctor --profile personal
```

`doctor` does not log in, select a file, upload a resume, or send a notification.

### 3. Bootstrap Login

```text
naukri-auto login --profile personal
```

Complete login, CAPTCHA, and MFA manually. Authentication remains in a dedicated local Playwright profile and must never be committed or shared.

If the profile is already authenticated, the command confirms it and exits automatically. Otherwise it waits for the login form, fills stored credentials when the current form is recognized, and leaves submission, CAPTCHA, and MFA to the user. Leave the browser open until the command verifies the profile and closes it.

### 4. Perform A Headed Dry Run

```text
naukri-auto run --profile personal --dry-run --headed
```

The dry-run branch stops before the upload method. It confirms authentication and looks for the resume upload control.

### 5. Perform A Controlled Upload

After the dry run succeeds:

```text
naukri-auto run --profile personal --headed
```

The command returns success only when the resulting profile UI provides update evidence. An attempted upload with an unknown result is not retried automatically.

## Windows Schedule

Review the configured local time and install the task:

```text
naukri-auto schedule install --profile personal
```

Other commands:

```text
naukri-auto schedule show --profile personal
naukri-auto schedule run-now --profile personal
naukri-auto schedule remove --profile personal
```

The task uses the current non-administrator user's interactive session, ignores overlapping runs, starts after a missed trigger when possible, can request wake-from-sleep, and stops after 30 minutes. It never runs as `SYSTEM`.

After changing a profile's schedule, run `schedule install` again to replace that profile's Windows task definition.

Because the dedicated browser profile belongs to the current user, remain signed in to Windows. Locking or sleeping the computer is acceptable when wake timers are enabled; signing out or powering off prevents the task from running.

## Command Reference

All profile-bound commands accept `--profile <name>`. The option may be omitted when a default profile is configured.

| Purpose | Command |
| --- | --- |
| Create a profile | `naukri-auto profile create <name> --username <login> --resume <path>` |
| List profiles | `naukri-auto profile list` |
| Inspect a profile | `naukri-auto profile show <name>` |
| Select the default | `naukri-auto profile default <name>` |
| Change username | `naukri-auto profile edit <name> --username <login>` |
| Change browser | `naukri-auto profile edit <name> --browser-channel chrome|msedge|chromium` |
| Change daily schedule | `naukri-auto profile edit <name> --schedule-frequency daily --schedule-time HH:MM` |
| Change weekly schedule | `naukri-auto profile edit <name> --schedule-frequency weekly --schedule-time HH:MM --schedule-days MON,FRI` |
| Check whether a password is stored | `naukri-auto credentials status --profile <name>` |
| Replace the stored password | `naukri-auto credentials update --profile <name>` |
| Remove the stored password | `naukri-auto credentials remove --profile <name>` |
| Import a résumé | `naukri-auto resume add <path> --profile <name> [--select] [--replace]` |
| List managed résumés | `naukri-auto resume list --profile <name>` |
| Select the active résumé | `naukri-auto resume select <filename> --profile <name>` |
| Remove an inactive résumé | `naukri-auto resume remove <filename> --profile <name>` |
| Check readiness | `naukri-auto doctor --profile <name>` |
| Establish or verify login | `naukri-auto login --profile <name>` |
| Safe browser test | `naukri-auto run --profile <name> --dry-run --headed` |
| Perform one upload | `naukri-auto run --profile <name> [--headed]` |
| Install the Windows task | `naukri-auto schedule install --profile <name>` |
| Inspect the Windows task | `naukri-auto schedule show --profile <name>` |
| Trigger the Windows task now | `naukri-auto schedule run-now --profile <name>` |
| Remove the Windows task | `naukri-auto schedule remove --profile <name>` |

Use `naukri-auto <command> --help` and `naukri-auto <command> <subcommand> --help` for exact options.

## Results And Diagnostics

Stable result categories include:

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

Each profile's mutable data directory holds its managed résumés, `last-result.json`, rotating logs, browser profile, and bounded failure artifacts. These files may contain private account context and stay outside the repository.

No automated flow bypasses CAPTCHA or MFA. When authentication cannot proceed safely, refresh it with `naukri-auto login --profile <name>`.

## Optional Notifications

Notifications are disabled by default and currently configured in the profile's generated `profile.toml`. Set a private ntfy-compatible HTTPS endpoint and topic:

```toml
[notification]
enabled = true
base_url = "https://ntfy.sh"
topic = "your-private-topic"
```

Run `doctor` after editing the file. Notification delivery is best-effort: it never changes a verified upload from success to failure. Do not put credentials, account details, or résumé content in the endpoint or topic.

## Updating An Existing Installation

From a clean checkout:

```bash
git pull --ff-only
source .venv/bin/activate  # PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
naukri-auto doctor --profile <name>
```

Existing profiles, managed résumés, keyring entries, and browser sessions are stored outside the repository and are not replaced by a Git update.

## Troubleshooting

- `AUTH_REQUIRED`: run `naukri-auto login --profile <name>` and complete any CAPTCHA or MFA.
- `SITE_CHANGED`: do not retry an upload blindly; inspect the timestamped screenshot and trace in the profile's `artifacts` directory.
- `UPLOAD_FAILED`: the upload outcome was not verified; inspect Naukri manually before retrying.
- `ALREADY_RUNNING`: another login or run owns the profile lock; wait for it to finish.
- Browser launch failure: install the configured Chrome/Edge channel, or select `chromium` and run `python -m playwright install chromium`.
- Windows task does not run: remain signed in, confirm wake timers, run `schedule show`, then use `schedule run-now` for a controlled check.

## Development Checks

The unit suite uses test doubles and performs no live network or browser calls:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
```

After installing development dependencies:

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Security

- Never commit a résumé, configuration, browser profile, cookies, logs, screenshots, traces, or credentials.
- Each teammate must create a separate local profile; do not share application-data directories, browser profiles, keyring entries, or diagnostic artifacts.
- Passwords live only in the OS keyring. `profile show` reports whether one is stored but never reads it into output.
- Profile login may fill stored credentials, but the user reviews and submits the login and completes CAPTCHA or MFA manually.
- Never place credentials in source code, TOML, `.env`, command-line arguments, or notifications.
- Treat diagnostic screenshots and traces as private local data.
- Review Naukri's applicable terms and account controls before enabling recurring execution.
