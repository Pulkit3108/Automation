# Windows Installation

Install Resume Automation as an isolated user-level CLI with `pipx`. The `resume-auto` command then
works from any PowerShell or Command Prompt window without activating a virtual environment.

## Requirements

- Windows 11
- Native Windows Python 3.12 or newer
- Google Chrome by default; Microsoft Edge is optional
- Internet access during installation and portal operations

Verify that `python` is a native Windows installation rather than MSYS2, Cygwin, or WSL:

```powershell
python --version
where.exe python
```

## Install pipx

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
```

Close and reopen the terminal once so the updated `PATH` is loaded.

## Install Resume Automation

```powershell
pipx install --python 3.12 git+https://github.com/Pulkit3108/resume-automation.git
resume-auto --version
```

`pipx` owns the isolated environment and exposes `resume-auto` globally. Do not create or activate a
repository `.venv` for ordinary use.

Continue with the shared [profile and usage workflow](README.md).

## Windows Scheduler Behavior

The task is named `ResumeAutomation-<profile>` and runs as the current interactive user with least
privilege. It supports multiple daily or selected-weekday triggers, ignores overlapping instances,
may wake the computer when enabled and supported, and stops after 30 minutes.

The account must be signed in. Locking the screen or turning off the display is supported. A time
missed while powered off is skipped; only the next future trigger runs. Compact status is available
through `schedule show`; use `schedule show --verbose` only for native diagnostics.

## Troubleshooting

- `pipx` is not recognized after `ensurepath`: close every terminal window and open a new one.
- `python` resolves to MSYS2/Cygwin/WSL: install native Windows Python and retry with that
  interpreter.
- Chrome launch fails: install the configured browser channel or explicitly select managed
  Chromium.
- Task installation fails: read the native error, then request verbose status only if the task was
  created.
- Task does not run: remain signed in, inspect compact status and the profile log, then use
  `schedule run-now` only when another real upload is intended.

See [install, update, and uninstall](install-update.md) for lifecycle commands.
