# First-Time Setup And Usage

Install the global `resume-auto` command first:

- [Windows installation](windows.md)
- [macOS and Linux installation](macos-linux.md)

Then complete the required steps below in order. Each successful command prints the next command.
No virtual-environment activation is required.

## Step 1: Create A Profile

```text
resume-auto profile create personal --provider naukri --username you@example.com --resume /absolute/path/resume.pdf
```

On Windows, use a quoted path such as `"C:\Users\you\Documents\resume.pdf"`. The password is
collected through a hidden prompt and stored in the OS keyring. The résumé is copied into managed
profile storage. The first profile automatically becomes the default; do not run `profile default`
unless you later create additional profiles.

Expected result:

```text
Profile created: personal
Default profile: personal
Next: resume-auto doctor --profile personal
```

## Step 2: Check Readiness

```text
resume-auto doctor --profile personal
```

This is read-only. Continue only when every check passes and the final line begins with `READY`.

## Step 3: Establish Login

```text
resume-auto login --profile personal
```

The command fills and submits a recognized login form. CAPTCHA and MFA remain manual. Invalid
credentials produce recovery commands; unknown pages stop and save private diagnostics.

Continue when the command reports `Login confirmed` or `Already authenticated`.

## Step 4: Run The Safe Dry Run

```text
resume-auto run --profile personal --dry-run --headed
```

The dry run checks authentication and the résumé control, then stops before selecting or uploading
a file. `--headed` keeps this first validation visible. Continue only after `DRY_RUN_SUCCESS`.

## Step 5: Perform One Controlled Upload

```text
resume-auto run --profile personal --headed
```

This changes the remote portal profile. Success requires new UI evidence. Never retry an unknown
outcome without checking the portal and private diagnostics first.

Continue only after `SUCCESS`.

## Step 6: Configure And Install Scheduling

Saving rules does not activate scheduling. Both commands are required:

```text
# Save rules: every day at 09:00 and 18:00
resume-auto schedule set --profile personal --times 09:00,18:00

# Install or replace the native scheduler job
resume-auto schedule install --profile personal
```

Enter `y` at the installation confirmation. Times use the local 24-hour `HH:MM` clock. To add a
separate selected-day rule before installation:

```text
resume-auto schedule add --profile personal --days MON,WED,FRI --times 13:30
```

Rules may use any combination of `MON,TUE,WED,THU,FRI,SAT,SUN`. Overlapping occurrences are
rejected. A profile supports up to 48 native triggers.

## Step 7: Verify The Installed Schedule

```text
resume-auto schedule show --profile personal
```

The compact output should show the profile, saved rules, native task/job, `Ready` or equivalent
status, and next run. Use `--verbose` only for native scheduler troubleshooting.

Setup is complete. The installed job survives terminal closure and reboot. Remain signed into the
same OS account before a scheduled time; a locked screen or inactive display is supported. Times
missed while powered off are skipped instead of replayed.

## Later: Update Profile Data

These are maintenance actions, not first-time setup steps:

```text
# Change username or email
resume-auto profile edit personal --username new-login@example.com

# Replace the password through a hidden prompt
resume-auto credentials update --profile personal

# Import and select a new résumé
resume-auto resume add /absolute/path/new-resume.pdf --profile personal --select

# Inspect the sanitized profile summary
resume-auto profile show personal

# Choose browser execution mode
resume-auto profile edit personal --background
resume-auto profile edit personal --headed
resume-auto profile edit personal --headless
```

Use `resume list`, `resume select`, and `resume remove` to manage inactive copies. Passwords are
never accepted as command arguments.

## Later: Manage Scheduling

```text
# Show saved rules
resume-auto schedule list --profile personal

# Show compact or native status
resume-auto schedule show --profile personal
resume-auto schedule show --profile personal --verbose

# Remove future scheduled runs but retain profile and rules
resume-auto schedule remove --profile personal

# Install retained rules again
resume-auto schedule install --profile personal
```

`schedule run-now` performs a real upload and should be used only as an intentional write.

## Diagnostics And Resource Behavior

- Native scheduling and a per-profile operating-system file lock prevent overlap. The operating
  system releases the lock when a process exits, including after a crash.
- Background mode runs a regular rendered browser outside the visible desktop; headed mode remains
  available for diagnosis, and headless mode remains available for portals that accept it.
- Each run reuses cookies/session data but creates and closes one browser process and context.
- Successful traces are discarded; failure artifacts follow the configured retention period.
- Logs rotate at 1 MB with five backups. Windows jobs have a 30-minute limit.
- Stable outcomes include `SUCCESS`, `DRY_RUN_SUCCESS`, `CONFIG_ERROR`, `AUTH_REQUIRED`,
  `ACCESS_DENIED`, `SITE_CHANGED`, `UPLOAD_FAILED`, `NETWORK_ERROR`, `ALREADY_RUNNING`,
  `DEPENDENCY_ERROR`, and `INTERNAL_ERROR`.

## Remove A Profile Completely

```text
resume-auto profile remove personal
```

After confirmation, this removes the native scheduler job, keyring credential, managed résumé
copies, browser session, configuration, logs, results, artifacts, lock, and default-profile pointer.
It does not remove the original source résumé.

For application updates and uninstall, see [install, update, and uninstall](install-update.md).
