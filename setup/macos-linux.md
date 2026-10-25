# macOS And Linux Installation

Install Resume Automation as an isolated user-level CLI with `pipx`. The `resume-auto` command then
works from any terminal without activating a virtual environment.

## Requirements

- Python 3.12 or newer
- Google Chrome by default
- macOS Keychain or a Linux Secret Service-compatible keyring
- `launchd` on macOS or a working `systemd --user` session on Linux

## Install pipx

macOS with Homebrew:

```bash
brew install pipx
pipx ensurepath
```

Ubuntu 23.04 or newer:

```bash
sudo apt update
sudo apt install pipx
pipx ensurepath
```

Fedora:

```bash
sudo dnf install pipx
pipx ensurepath
```

Close and reopen the terminal once so the updated `PATH` is loaded.

## Install Resume Automation

```bash
pipx install git+https://github.com/Pulkit3108/resume-automation.git
resume-auto --version
```

Continue with the shared [profile and usage workflow](README.md).

## macOS Scheduling

`schedule install` writes a per-user LaunchAgent under:

```text
~/Library/LaunchAgents/com.resumeautomation.<profile>.plist
```

The signed-in GUI session owns the job. Scheduler stdout and stderr go to the profile log directory.
A locked screen or inactive display is supported. Events missed while powered off are skipped.

## Linux Scheduling

`schedule install` writes per-user service and timer units under:

```text
~/.config/systemd/user/resume-automation-<profile>.service
~/.config/systemd/user/resume-automation-<profile>.timer
```

The non-catch-up timer is enabled immediately. A graphical signed-in session is normally required
for Secret Service and the dedicated browser profile.

## Browser Choice

The default `chrome` channel uses installed Google Chrome. To use managed Chromium instead:

```text
resume-auto profile edit personal --browser-channel chromium
python -m playwright install chromium
```

macOS explicitly enables Chromium sandboxing. Linux retains Playwright's platform default because
container and distribution requirements vary.

## Troubleshooting

- Secure credential storage unavailable on Linux: configure a Secret Service-compatible keyring;
  the application never falls back to plaintext.
- Chrome launch fails: install the selected channel or use managed Chromium.
- Scheduler unavailable: confirm `launchctl` on macOS or `systemctl --user` on Linux, then rerun
  `doctor`.
- Scheduled run fails: inspect compact status and the profile log before requesting native verbose
  diagnostics.

See [install, update, and uninstall](install-update.md) for lifecycle commands.
