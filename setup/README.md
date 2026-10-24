# Setup And Usage

Complete the platform installation first:

- [Windows](windows.md)
- [macOS and Linux](macos-linux.md)

The commands below are shared across supported operating systems. Run them inside the activated
project virtual environment.

## 1. Create A Profile

```text
naukri-auto profile create personal --username you@example.com --resume /absolute/path/resume.pdf
```

On Windows, use a quoted Windows path such as `"C:\Users\you\Documents\resume.pdf"`. The command
prompts for the password without displaying it and stores it in the OS keyring. It copies the
résumé into managed profile storage, so the source file can later move without breaking the profile.

The first profile becomes the default. With multiple profiles, pass `--profile <name>` or choose a
default:

```text
naukri-auto profile default personal
```

## 2. Check Readiness

```text
naukri-auto doctor --profile personal
```

`doctor` checks Python, configuration, managed résumé, keyring, Playwright, browser launch, native
scheduler availability, and local data paths. It does not log in, upload, or send notifications.

## 3. Establish Login

```text
naukri-auto login --profile personal
```

The command reuses a dedicated browser profile, fills and submits a recognized login form, and
closes after authentication. CAPTCHA and MFA remain manual. Invalid credentials produce exact
username/password recovery commands. Unknown page contracts stop after the configured timeout and
save a private local screenshot and Playwright trace.

## 4. Perform A Dry Run

```text
naukri-auto run --profile personal --dry-run --headed
```

The dry run confirms authentication and the résumé control, then stops before file selection or
upload.

## 5. Perform One Controlled Upload

```text
naukri-auto run --profile personal --headed
```

Success requires new UI evidence: a success message, a newly appearing filename, or changed update
evidence. Do not retry when the outcome is unknown; inspect Naukri and the local artifacts first.

## Update Profile Data

```text
# Change login email or username
naukri-auto profile edit personal --username new-login@example.com

# Replace the password through a hidden prompt
naukri-auto credentials update --profile personal

# Import and select a new résumé
naukri-auto resume add /absolute/path/new-resume.pdf --profile personal --select

# Inspect the sanitized profile summary
naukri-auto profile show personal
```

Use `resume list`, `resume select`, and `resume remove` to manage inactive copies. Passwords are
never accepted as command arguments.

## Configure Scheduling

Times use the local 24-hour `HH:MM` clock. Omitting `--days` means every day.

```text
# Replace all rules: every day at 09:00 and 18:00
naukri-auto schedule set --profile personal --times 09:00,18:00

# Add selected-day rules
naukri-auto schedule add --profile personal --days MON,WED,FRI --times 13:30
naukri-auto schedule add --profile personal --days SUN --times 10:15

# Review and install once
naukri-auto schedule list --profile personal
naukri-auto schedule install --profile personal
```

Rules may use any combination of `MON,TUE,WED,THU,FRI,SAT,SUN`. Overlapping occurrences are
rejected. A profile supports up to 48 native triggers.

Inspect the compact status by default, or request native diagnostics:

```text
naukri-auto schedule show --profile personal
naukri-auto schedule show --profile personal --verbose
```

`schedule run-now` performs a real upload and should be used only as an intentional controlled
write. Stop future runs without deleting the profile by removing the native job:

```text
naukri-auto schedule remove --profile personal
```

The configured rules remain available and can be installed again later.

## Persistence And Resource Behavior

- Installed jobs survive terminal closure and reboot. Missed times while powered off are skipped;
  only the next future rule runs.
- Sign in to the same OS account before a scheduled time so the keyring and browser profile are
  available. A locked screen or inactive display does not block a headless run.
- Native scheduling and a per-profile process lock prevent overlap. Missed occurrences are not
  replayed as a backlog.
- Each run reuses cookies/session data but creates and closes one browser process and context.
- Successful traces are discarded. Failure artifacts follow the configured retention period.
- Logs rotate at 1 MB with five backups. Windows jobs have a 30-minute execution limit.

## Results And Diagnostics

Run results include `SUCCESS`, `DRY_RUN_SUCCESS`, `CONFIG_ERROR`, `AUTH_REQUIRED`, `SITE_CHANGED`,
`UPLOAD_FAILED`, `NETWORK_ERROR`, `ALREADY_RUNNING`, `DEPENDENCY_ERROR`, and `INTERNAL_ERROR`.

Each profile stores rotating logs, `last-result.json`, and bounded failure artifacts in its
platform-specific mutable-data directory. These files can contain private account context and must
not be committed or shared without review.

## Optional Notifications

Notifications are disabled by default. A private ntfy-compatible HTTPS endpoint and topic may be
configured in the generated profile TOML. Run `doctor` after editing it. Notification failure never
changes a verified upload into a failure.

## Remove A Profile Completely

```text
naukri-auto profile remove personal
```

After confirmation, this removes the native scheduler job, keyring credential, managed résumé
copies, browser session, configuration, logs, results, artifacts, lock, and default-profile pointer.
It does not remove the repository or original source résumé.
