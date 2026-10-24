# macOS And Linux Setup

Use Python 3.12 or newer and an installed Chrome browser. macOS uses Keychain and a per-user
`launchd` agent. Linux requires a Secret Service-compatible keyring and uses `systemd --user`.

## Install

Run from the repository root:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Continue with the shared [profile and usage workflow](README.md).

## macOS Scheduling

`schedule install` writes a per-user LaunchAgent under:

```text
~/Library/LaunchAgents/com.naukri-resume-automation.<profile>.plist
```

The agent is loaded into the signed-in GUI session. Scheduler stdout and stderr are written to the
profile log directory. A locked screen or inactive display is supported; sign in after reboot so
Keychain and the browser profile are available.

## Linux Scheduling

`schedule install` writes per-user service and timer units under:

```text
~/.config/systemd/user/naukri-resume-automation-<profile>.service
~/.config/systemd/user/naukri-resume-automation-<profile>.timer
```

The timer is enabled immediately and uses persistent calendar rules. Application output remains in
the profile's rotating log; native unit diagnostics are available through `schedule show --verbose`
or the user journal. A graphical signed-in session is normally required for Secret Service and the
dedicated browser profile.

## Browser Choice

The default `chrome` channel uses installed Google Chrome. Select installed Edge where supported or
use Playwright-managed Chromium explicitly:

```text
naukri-auto profile edit personal --browser-channel chromium
python -m playwright install chromium
```

macOS desktop launches explicitly enable Chromium sandboxing. Linux retains Playwright's platform
default because container and distribution sandbox requirements vary.

## Update An Existing Checkout

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install -e .
naukri-auto doctor --profile personal
```

## macOS And Linux Troubleshooting

- Secure credential storage unavailable on Linux: configure a Secret Service-compatible keyring;
  the application will not fall back to plaintext.
- Chrome launch fails: install the selected browser channel or use managed Chromium as shown above.
- Scheduler unavailable: confirm `launchctl` on macOS or a working `systemctl --user` session on
  Linux, then rerun `doctor`.
- Scheduled run fails: inspect the compact schedule status and profile log before requesting native
  verbose diagnostics.
