# Naukri Resume Automation

A cross-platform Python application for updating a configured resume on Naukri at chosen times.

The application performs one run and exits. Windows Task Scheduler, macOS `launchd`, or Linux
`systemd --user` owns the schedule, so no Python process remains running all day.

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
- native persistent scheduling on Windows, macOS, and Linux with independent day-and-time rules.

See [DESIGN.md](DESIGN.md) for architecture and safety boundaries.

## Requirements

- Python 3.12 or newer;
- Google Chrome by default, or Microsoft Edge / Playwright-managed Chromium when configured;
- Windows 11, macOS, or a systemd-based Linux distribution for automatic scheduling;
- internet access when installing dependencies and running Naukri automation.

Linux credential storage requires a working Secret Service-compatible keyring. If no secure backend is available, profile creation fails instead of storing a password insecurely.

## Windows Installation

Run in PowerShell from this repository:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Use native Windows CPython 3.12 or newer. If `where.exe python` resolves only to an MSYS2,
Cygwin, or WSL interpreter, install native Windows Python first; a correct Windows virtual
environment contains `.venv\Scripts\python.exe`, not `.venv\bin\python`.

If PowerShell reports that script execution is disabled, enable locally created scripts for the
current Windows user, then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

An organization-managed execution policy may override this setting. In that case, do not bypass
the managed policy; use Command Prompt with `.venv\Scripts\activate.bat`, or run the virtual
environment executable directly as `.\.venv\Scripts\python.exe`.

Keep this checkout and its virtual environment at the same absolute paths after installing the
scheduled task. The task records the virtual environment's absolute Python path, and the editable
installation refers back to this checkout.

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

On Windows and macOS desktop runs, the application explicitly enables Playwright's Chromium
sandbox. Linux retains Playwright's platform default because container and distribution
requirements vary.

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

Every profile has separate configuration, managed résumés, browser cookies, logs, artifacts, lock,
result, keyring entry, and native scheduler job. Two local profiles using the same Naukri username
still modify the same remote Naukri account, so do not schedule them at overlapping times.

### Update Or Remove A Profile

Use commands rather than editing application-data files manually:

```text
naukri-auto profile edit personal --username new-login@example.com
naukri-auto credentials update --profile personal
naukri-auto resume add C:\Users\you\Documents\new-resume.pdf --profile personal --select
naukri-auto profile remove personal
```

Password updates always use a hidden prompt. Résumé updates copy the selected source into managed
profile storage. `profile remove` asks for confirmation, removes the native scheduler job and all
managed profile data, deletes the keyring credential, and clears the default-profile pointer. It
does not delete the repository or the original source résumé.

### 2. Check Local Readiness

```text
naukri-auto doctor --profile personal
```

`doctor` does not log in, select a file, upload a resume, or send a notification.

### 3. Bootstrap Login

```text
naukri-auto login --profile personal
```

The command fills and submits a recognized login form using the profile's stored credentials.
Authentication remains in a dedicated local Playwright profile and must never be committed or
shared. CAPTCHA and MFA remain manual.

If the profile is already authenticated, the command confirms it and exits. If Naukri rejects the
email or password, the browser closes and the command prints the exact credential and username
update commands. A recognized CAPTCHA or MFA challenge stays open for manual completion. Unknown
login outcomes stop after the configured timeout instead of waiting indefinitely and save a local
screenshot and Playwright trace under the profile's artifacts directory.

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

The command returns as soon as any valid post-upload success message, newly appearing filename, or
changed update evidence is observed. An attempted upload with an unknown result is not retried
automatically.

## Schedule

Use `schedule set` to replace the profile's rules. Omitting `--days` means every day:

```text
naukri-auto schedule set --profile personal --times 09:00,18:00
```

Use `schedule add` for independent selected-day rules:

```text
naukri-auto schedule add --profile personal --days MON,WED,FRI --times 13:30
naukri-auto schedule add --profile personal --days SUN --times 10:15
naukri-auto schedule list --profile personal
```

Times use local 24-hour `HH:MM` format. Rules may target every day or any combination of
`MON,TUE,WED,THU,FRI,SAT,SUN`. Overlapping rules are rejected, and a profile supports up to 48
native triggers, matching the Windows platform limit. This provides cron-like flexibility without
raw cron expressions or a resident Python process.

Install the configured rules once:

```text
naukri-auto schedule install --profile personal
```

Other commands:

```text
naukri-auto schedule show --profile personal
naukri-auto schedule run-now --profile personal
naukri-auto schedule remove --profile personal
```

The installed job persists after terminal closure and reboot. The user must sign in after a reboot
so the operating-system keyring and dedicated browser profile are available. Screen lock, display
sleep, or inactivity do not disable a scheduled headless run. A powered-off computer cannot run;
native schedulers may consolidate or catch up missed runs after wake or login.

After changing rules, run `schedule install` again to replace that profile's native scheduler
definition.

| Platform | Persistent scheduler | Installed definition |
| --- | --- | --- |
| Windows | Task Scheduler, current interactive user | `NaukriResumeAutomation-<profile>` |
| macOS | Per-user `launchd` agent | `~/Library/LaunchAgents/com.naukri-resume-automation.<profile>.plist` |
| Linux | Per-user systemd service and timer | `~/.config/systemd/user/naukri-resume-automation-<profile>.*` |

## Command Reference

All profile-bound commands accept `--profile <name>`. The option may be omitted when a default profile is configured.

| Purpose | Command |
| --- | --- |
| Create a profile | `naukri-auto profile create <name> --username <login> --resume <path>` |
| List profiles | `naukri-auto profile list` |
| Inspect a profile | `naukri-auto profile show <name>` |
| Select the default | `naukri-auto profile default <name>` |
| Remove a profile and its managed data | `naukri-auto profile remove <name>` |
| Change username | `naukri-auto profile edit <name> --username <login>` |
| Change browser | `naukri-auto profile edit <name> --browser-channel chrome\|msedge\|chromium` |
| Replace schedule rules | `naukri-auto schedule set --profile <name> --times HH:MM,HH:MM [--days MON,FRI]` |
| Add a schedule rule | `naukri-auto schedule add --profile <name> --times HH:MM,HH:MM [--days MON,FRI]` |
| List schedule rules | `naukri-auto schedule list --profile <name>` |
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
| Install the native scheduler job | `naukri-auto schedule install --profile <name>` |
| Inspect the scheduler job | `naukri-auto schedule show --profile <name>` |
| Trigger the scheduler job now | `naukri-auto schedule run-now --profile <name>` |
| Remove the scheduler job | `naukri-auto schedule remove --profile <name>` |

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
source .venv/bin/activate  # PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
naukri-auto doctor --profile <name>
```

Existing profiles, managed résumés, keyring entries, and browser sessions are stored outside the repository and are not replaced by a Git update.

## Troubleshooting

- `AUTH_REQUIRED`: run `naukri-auto login --profile <name>` and complete any CAPTCHA or MFA.
- Login reports invalid email or password: run `naukri-auto credentials update --profile <name>`
  for the password or `naukri-auto profile edit <name> --username <login>` for the email, then retry.
- Login page is not recognized: the command stops, prints local log and artifact paths, and saves a
  screenshot and trace. Hidden CAPTCHA markup is not treated as an active challenge.
- `SITE_CHANGED`: do not retry an upload blindly; inspect the timestamped screenshot and trace in the profile's `artifacts` directory.
- `UPLOAD_FAILED`: the upload outcome was not verified; inspect Naukri manually before retrying.
- `ALREADY_RUNNING`: another login or run owns the profile lock; wait for it to finish.
- Browser launch failure: install the configured Chrome/Edge channel, or select `chromium` and run `python -m playwright install chromium`.
- PowerShell blocks `Activate.ps1`: apply the current-user `RemoteSigned` command from
  [Windows Installation](#windows-installation), unless an organization-managed policy overrides it.
- Scheduled job does not run: remain signed in, run `schedule show`, inspect the profile log, then
  use `schedule run-now` for a controlled check.

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
