# Resume Automation

A cross-platform Python CLI that safely updates a managed résumé on a configured job-portal profile
and exits. Naukri is the first provider; additional portals can be added behind the provider
contract without changing profile, scheduling, credential, result, or browser lifecycle code.
Native operating-system schedulers provide persistent execution without keeping a Python daemon or
browser process running all day.

## What It Provides

- isolated named profiles with separate credentials, résumés, browser sessions, logs, and schedules;
- explicit portal-provider selection with isolated provider-specific browser behavior;
- passwords stored only in Windows Credential Manager, macOS Keychain, or a secure Linux keyring;
- interactive login with automatic recognized-form submission and manual CAPTCHA/MFA handling;
- side-effect-free readiness checks and dry runs;
- one-shot résumé uploads with post-upload verification and no blind retries;
- independent everyday and selected-weekday schedule rules with multiple local times;
- native persistent scheduling through Windows Task Scheduler, macOS `launchd`, or Linux
  `systemd --user`;
- compact status output, opt-in native diagnostics, rotating logs, and bounded failure artifacts;
- confirmed profile cleanup that leaves the repository and original source résumé untouched.

## Supported Platforms

| Platform | Manual runs | Persistent scheduler | Credential storage |
| --- | --- | --- | --- |
| Windows 11 | Yes | Task Scheduler | Windows Credential Manager |
| macOS | Yes | Per-user `launchd` agent | macOS Keychain |
| Linux with systemd | Yes | Per-user systemd timer | Secret Service-compatible keyring |

Python 3.12 or newer and an installed Google Chrome browser are the defaults. Microsoft Edge and a
Playwright-managed Chromium browser are optional alternatives.

## Get Started

Choose the operating-system guide:

- [Windows setup](setup/windows.md)
- [macOS and Linux setup](setup/macos-linux.md)

After installation, use the shared [profile, upload, scheduling, update, and cleanup workflow](setup/README.md).

For upgrades or removal, see [install, update, and uninstall](setup/install-update.md).

## Documentation

| Document | Scope |
| --- | --- |
| [Setup and usage](setup/README.md) | Cross-platform commands and lifecycle |
| [Windows setup](setup/windows.md) | Native Python, PowerShell, and Task Scheduler |
| [macOS and Linux setup](setup/macos-linux.md) | Keyring, `launchd`, and systemd user setup |
| [Install, update, and uninstall](setup/install-update.md) | pipx application lifecycle |
| [Design](DESIGN.md) | Architecture, safety invariants, concurrency, and resource lifecycle |
| [Contributing](CONTRIBUTING.md) | Clone-based development and verification |
| [Agent instructions](AGENTS.md) | Repository maintenance and verification rules |
| [Example configuration](config.example.toml) | Generated profile configuration shape |

## Safety Summary

- A real `run` changes the configured remote portal profile; use `--dry-run` before the first upload on a
  machine or account.
- CAPTCHA and MFA are always manual and are never bypassed.
- Passwords never belong in source, TOML, environment files, command arguments, logs, or
  notifications.
- An upload is successful only after the profile UI supplies new post-upload evidence.
- An unknown upload outcome is never retried automatically.
- Browser profiles, cookies, résumés, logs, screenshots, traces, and results remain outside Git.

## License

This project is licensed under the [MIT License](LICENSE).
