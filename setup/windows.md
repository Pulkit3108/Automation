# Windows Installation

Install Resume Automation as an isolated user-level CLI with `pipx`. The `resume-auto` command then
works from any PowerShell or Command Prompt window without activating a virtual environment.

## Requirements

- Windows 11
- Native Windows Python 3.12 or newer, including newer supported releases such as 3.15
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

`pipx ensurepath` may report two PATH additions: Python's user `Scripts` directory and pipx's
application directory. That is normal. Its generic `source ~/.bashrc` suggestion is for Unix shells
and does not apply to Windows PowerShell; reopening PowerShell is the correct action.

## Install Resume Automation

```powershell
pipx install git+https://github.com/Pulkit3108/resume-automation.git
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

The default `background` browser mode runs regular rendered Chrome outside the visible desktop and
marks its window as a Windows tool window so it does not remain in the taskbar. The scheduled task
uses `pythonw.exe`, which avoids opening a console window. Use
`resume-auto profile edit personal --headed` for visual diagnosis or `--headless` only when the
configured portal accepts true headless browsing. Reinstall the schedule after upgrading from a
version earlier than 0.2.4 so its action changes from `python.exe` to `pythonw.exe`.

## Troubleshooting

- `pipx` is not recognized after `ensurepath`: close every terminal window and open a new one.
- `ensurepath` mentions `source ~/.bashrc`: ignore that Unix-only suggestion on Windows and reopen
  PowerShell.
- `python` resolves to MSYS2/Cygwin/WSL: install native Windows Python and retry with that
  interpreter.
- Chrome launch fails: install the configured browser channel or explicitly select managed
  Chromium.
- Task installation fails: read the native error, then request verbose status only if the task was
  created.
- Task does not run: remain signed in, inspect compact status and the profile log, then use
  `schedule run-now` only when another real upload is intended.
- `ACCESS_DENIED`: inspect the retained screenshot and trace. Do not confuse a portal denial page
  with a changed résumé selector.

See [install, update, and uninstall](install-update.md) for lifecycle commands.
