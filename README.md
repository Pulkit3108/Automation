# Naukri Resume Automation

A Windows-first, cross-platform Python application for updating a configured resume on Naukri at a chosen time.

The application performs one run and exits. Windows Task Scheduler owns the schedule, so no Python process needs to remain running all day. Manual runs are supported on Windows, macOS, and Linux.

> [!IMPORTANT]
> Browser selectors have not yet been calibrated against a live Naukri account. Start with interactive login and `--dry-run`. A real upload is an external profile change and should be attempted only after the dry run succeeds.

## Current Status

Implemented:

- typed TOML configuration with resume validation;
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

- install dependencies and Chromium on a target system;
- calibrate current Naukri login/profile selectors through a headed dry run;
- validate Windows Task Scheduler registration on Windows 11;
- authorize and perform one controlled live upload.

See [DESIGN.md](DESIGN.md) for architecture, safety boundaries, and delivery phases.

## Requirements

- Python 3.12 or newer;
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
python -m playwright install chromium
```

Keep this virtual environment after installing the scheduled task. The task records the absolute Python interpreter path used during installation.

## macOS Or Linux Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
```

Automatic scheduler installation is currently Windows-only. The application commands themselves are cross-platform.

## First-Time Setup

### 1. Configure

```text
naukri-auto configure
```

The configuration contains only non-secret settings such as the absolute resume path, schedule, and optional notification target.

Default locations:

| Platform | Configuration | Mutable data |
| --- | --- | --- |
| Windows | `%APPDATA%\NaukriAutomation\config.toml` | `%LOCALAPPDATA%\NaukriAutomation\` |
| macOS | `~/Library/Application Support/NaukriAutomation/config.toml` | same application-support directory |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/NaukriAutomation/config.toml` | `${XDG_STATE_HOME:-~/.local/state}/NaukriAutomation/` |

You can inspect [config.example.toml](config.example.toml) before configuration.

### 2. Check Local Readiness

```text
naukri-auto doctor
```

`doctor` does not log in, select a file, upload a resume, or send a notification.

### 3. Bootstrap Login

```text
naukri-auto login --headed
```

Complete login, CAPTCHA, and MFA manually. Authentication remains in a dedicated local Playwright profile and must never be committed or shared.

### 4. Perform A Headed Dry Run

```text
naukri-auto run --dry-run --headed
```

The dry-run branch stops before the upload method. It confirms authentication and looks for the resume upload control.

### 5. Perform A Controlled Upload

After the dry run succeeds:

```text
naukri-auto run --headed
```

The command returns success only when the resulting profile UI provides update evidence. An attempted upload with an unknown result is not retried automatically.

## Windows Schedule

Review the configured local time and install the task:

```text
naukri-auto schedule install
```

Other commands:

```text
naukri-auto schedule show
naukri-auto schedule run-now
naukri-auto schedule remove
```

The task uses the current non-administrator user's interactive session, ignores overlapping runs, starts after a missed trigger when possible, can request wake-from-sleep, and stops after 30 minutes. It never runs as `SYSTEM`.

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

The mutable data directory holds `last-result.json`, rotating logs, the browser profile, and bounded failure artifacts. These files may contain private account context and stay outside the repository.

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

- Never commit a resume, configuration, browser profile, cookies, logs, screenshots, traces, or credentials.
- Never place credentials in source code, TOML, `.env`, command-line arguments, or notifications.
- Treat diagnostic screenshots and traces as private local data.
- Review Naukri's applicable terms and account controls before enabling recurring execution.
