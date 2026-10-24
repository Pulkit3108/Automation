# Windows Setup

Use native Windows CPython 3.12 or newer, an installed Chrome browser, and Windows PowerShell.

## Verify Native Python

```powershell
python --version
where.exe python
```

The interpreter must be a native Windows installation, not MSYS2, Cygwin, or WSL. A correct Windows
virtual environment contains `.venv\Scripts\python.exe`; a `.venv\bin\python` layout indicates the
wrong interpreter.

## Install

Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

If PowerShell blocks `Activate.ps1`, permit locally created scripts for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

An organization-managed policy may override this setting. Do not bypass managed policy; use Command
Prompt with `.venv\Scripts\activate.bat` or invoke `.\.venv\Scripts\python.exe` directly.

Keep the checkout and `.venv` at the same absolute paths after scheduler installation. The task
records the virtual environment's Python path, and the editable installation refers to this source.

Continue with the shared [profile and usage workflow](README.md).

## Windows Scheduler Behavior

The task is named `NaukriResumeAutomation-<profile>` and runs as the current interactive user with
least privilege. It supports multiple daily or selected-weekday triggers, ignores overlapping task
instances, may wake the computer when enabled and supported, and stops after 30 minutes.

The account must be signed in. Locking the screen or turning off the display is supported. A time
missed while powered off is skipped rather than replayed after startup; the next future trigger runs
normally. Compact status is available through `schedule show`; use
`schedule show --verbose` only for native `schtasks.exe` diagnostics.

## Update An Existing Checkout

```powershell
git pull --ff-only
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
naukri-auto doctor --profile personal
```

An editable installation usually sees source-only updates immediately. Re-running `pip install -e .`
also picks up packaging or dependency changes safely.

## Windows Troubleshooting

- `python` creates `.venv\bin`: install native Windows Python and recreate only `.venv`.
- PowerShell blocks activation: use the current-user `RemoteSigned` command above.
- Browser warning mentions `--no-sandbox`: update to the latest repository version; Windows desktop
  launches explicitly enable Chromium sandboxing.
- Task installation fails: read the exact native error, then use `schedule show --verbose` only if
  the task exists.
- Task does not run: remain signed in, inspect compact status and the profile log, then use
  `schedule run-now` only if another real upload is intended.
