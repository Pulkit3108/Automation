# Install, Update, And Uninstall

Resume Automation is installed with `pipx`, which owns a private environment and exposes
`resume-auto` globally on `PATH`.

## Install Latest Main

```text
pipx install --python 3.12 git+https://github.com/Pulkit3108/resume-automation.git
```

Use the platform guide to install `pipx` first:

- [Windows](windows.md)
- [macOS and Linux](macos-linux.md)

## Update To The Latest Functionality

Run outside a scheduled execution window:

```text
pipx reinstall resume-automation
resume-auto --version
resume-auto doctor --profile personal
```

`pipx reinstall` reuses the original Git source and rebuilds the isolated environment. Profile
configuration, credentials, managed résumés, browser sessions, logs, artifacts, and schedule rules
live outside the installation and remain intact.

Reinstall each native scheduler job once after an application update so it records the current pipx
interpreter path:

```text
resume-auto schedule install --profile personal
```

The install replaces an existing native job in place; removal is not required first.

## Inspect Installation

```text
pipx list
resume-auto --version
resume-auto doctor --profile personal
```

## Uninstall The Application Only

Stop future native runs first, then uninstall the CLI:

```text
resume-auto schedule remove --profile personal
pipx uninstall resume-automation
```

Profile state remains on disk for a later reinstall.

## Remove Everything

```text
resume-auto profile remove personal
pipx uninstall resume-automation
```

The confirmed profile removal deletes managed local state and the keyring credential. It does not
delete the original source résumé.
