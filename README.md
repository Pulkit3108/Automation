# Naukri Resume Automation

A Windows-first, cross-platform Python application for updating a configured resume on Naukri at a chosen time.

The application performs one run and exits. Windows Task Scheduler owns the schedule, so no Python process needs to remain running all day. Manual runs are supported on Windows, macOS, and Linux.

> [!IMPORTANT]
> Browser selectors have not yet been calibrated against a live Naukri account. Start with interactive login and `--dry-run`. A real upload is an external profile change and should be attempted only after the dry run succeeds.

## Current Status

Implemented:

- isolated named profiles with typed configuration and managed résumé collections;
- OS-keyring credential storage with hidden password prompts;
- platform-appropriate configuration and data directories;
- dedicated Playwright browser profile;
- interactive login bootstrap;
- side-effect-safe `doctor` and `run --dry-run` commands;
- one-shot upload workflow with post-upload verification;
- sanitized results, rotating logs, screenshots, and Playwright traces;
- overlapping-run protection and artifact retention;
- optional ntfy-compatible notification delivery;
- Windows Task Scheduler XML and task management commands;
- isolated tests that require no browser or network.

Still requires environment validation:

- install dependencies and confirm the selected browser on a target system;
- calibrate current Naukri login/profile selectors through a headed dry run;
- validate Windows Task Scheduler registration on Windows 11;
- authorize and perform one controlled live upload.

See [DESIGN.md](DESIGN.md) for architecture, safety boundaries, and delivery phases.

## Requirements

- Python 3.12 or newer;
- Google Chrome by default, or Microsoft Edge / Playwright-managed Chromium when configured;
- Windows 11 for automatic schedule management;
- macOS or Linux for manual commands and development;
- internet access when installing dependencies and running Naukri automation.

The computer must be running or sleeping with wake timers enabled. A fully powered-off computer cannot execute the schedule.

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

Automatic scheduler installation is currently Windows-only. The application commands themselves are cross-platform.

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

The first profile becomes the default. With multiple profiles, use `--profile <name>` or select a default with `naukri-auto profile default <name>`.

Profile and résumé management:

```text
naukri-auto profile list
naukri-auto profile show personal
naukri-auto profile edit personal --schedule-time 09:00
naukri-auto credentials update --profile personal
naukri-auto resume add --profile personal C:\path\alternate-resume.pdf
naukri-auto resume list --profile personal
naukri-auto resume select --profile personal alternate-resume.pdf
```

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

Because the dedicated browser profile belongs to the current user, remain signed in to Windows. Locking or sleeping the computer is acceptable when the Windows power settings allow wake timers; signing out is not.

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

No automated flow bypasses CAPTCHA or MFA. When authentication cannot proceed safely, refresh it with `naukri-auto login --headed`.

## Development Checks

The unit suite uses only Python's standard library and performs no network or browser calls:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
```

After installing development dependencies:

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Legacy Files

The original Selenium scripts remain temporarily at the repository root as migration evidence. They are not used by the new package and must not be run; some contain obsolete APIs and live external side effects. Remove or archive them only after the new headed dry run succeeds.

## Security

- Never commit a résumé, configuration, browser profile, cookies, logs, screenshots, traces, or credentials.
- Passwords live only in the OS keyring. `profile show` reports whether one is stored but never reads it into output.
- Profile login may fill stored credentials, but the user reviews and submits the login and completes CAPTCHA or MFA manually.
- Never place credentials in source code, TOML, `.env`, command-line arguments, or notifications.
- Treat diagnostic screenshots and traces as private local data.
- Review Naukri's applicable terms and account controls before enabling recurring execution.
