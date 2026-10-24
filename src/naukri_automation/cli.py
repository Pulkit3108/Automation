from __future__ import annotations

import argparse
import importlib.util
import logging
import logging.handlers
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from naukri_automation import __version__
from naukri_automation.browser_session import BrowserDependencyError, BrowserSession
from naukri_automation.config import AppConfig, ConfigurationError, load_config
from naukri_automation.credentials import CredentialStore
from naukri_automation.naukri_site import AuthState, NaukriSite
from naukri_automation.paths import AppPaths, ProfilePaths, get_app_paths
from naukri_automation.profile_cli import add_management_parsers, handle_management_command
from naukri_automation.profile_store import resolve_profile_name
from naukri_automation.run_lock import AlreadyRunningError, RunLock
from naukri_automation.schedule_cli import add_schedule_parser, handle_schedule
from naukri_automation.scheduling import SchedulerError
from naukri_automation.workflow import execute

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="naukri-auto",
        description="Safely update a Naukri resume from a scheduled one-shot command.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    add_management_parsers(commands)

    doctor = commands.add_parser("doctor", help="run side-effect-free local readiness checks")
    doctor.add_argument("--profile")
    login = commands.add_parser("login", help="open a headed browser for interactive Naukri login")
    login.add_argument("--profile")
    login.add_argument("--headed", action="store_true", help=argparse.SUPPRESS)

    run = commands.add_parser("run", help="perform one resume-update workflow")
    run.add_argument("--profile")
    run.add_argument("--dry-run", action="store_true", help="stop before selecting a file")
    run.add_argument("--headed", action="store_true", help="show the browser window")

    add_schedule_parser(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app_paths = get_app_paths()

    try:
        if args.command in {"profile", "credentials", "resume"}:
            _configure_logging(app_paths, verbose=args.verbose)
            return handle_management_command(args, app_paths)

        profile_name = resolve_profile_name(app_paths, getattr(args, "profile", None))
        runtime_paths = app_paths.profile(profile_name)
        config_path = runtime_paths.config_file
        _configure_logging(runtime_paths, verbose=args.verbose)

        if args.command == "doctor":
            return _doctor(config_path, runtime_paths, profile_name)
        if args.command == "login":
            return _login(config_path, runtime_paths, profile_name)
        if args.command == "run":
            config = load_config(config_path)
            result = execute(
                config,
                runtime_paths,
                dry_run=args.dry_run,
                headed=args.headed,
            )
            print(f"{result.outcome.value}: {result.message}")
            if result.artifact_dir:
                print(f"Artifacts: {result.artifact_dir}")
            return result.exit_code
        if args.command == "schedule":
            return handle_schedule(
                args,
                config_path,
                runtime_paths,
                profile_name,
                python_executable=Path(sys.executable),
            )
    except (ConfigurationError, SchedulerError, BrowserDependencyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    return 2


def _doctor(
    config_path: Path,
    paths: ProfilePaths,
    profile_name: str,
) -> int:
    checks: list[tuple[str, bool, str]] = []
    config: AppConfig | None = None
    checks.append(("Python", sys.version_info >= (3, 12), sys.version.split()[0]))
    checks.append(("Configuration", config_path.is_file(), str(config_path)))
    try:
        config = load_config(config_path)
        checks.append(("Configuration schema", True, "valid"))
        checks.append(("Resume", True, f"{config.resume_path.name} is readable"))
        managed = config.resume_path.parent.resolve() == paths.resumes.resolve()
        checks.append(("Managed résumé", managed, str(config.resume_path)))
    except ConfigurationError as error:
        checks.append(("Configuration schema", False, str(error)))
    try:
        credential_stored = CredentialStore().has(profile_name)
        checks.append(
            (
                "OS keyring credential",
                credential_stored,
                "stored" if credential_stored else "not stored",
            )
        )
    except ConfigurationError as error:
        checks.append(("OS keyring credential", False, str(error)))
    playwright_present = importlib.util.find_spec("playwright") is not None
    checks.append(
        (
            "Playwright package",
            playwright_present,
            "installed" if playwright_present else "install project dependencies",
        )
    )
    if playwright_present:
        browser_channel = config.browser_channel if config is not None else "chrome"
        browser_ready, browser_detail = _playwright_browser_check(browser_channel)
        checks.append((f"Browser ({browser_channel})", browser_ready, browser_detail))
    scheduler_command = (
        "schtasks.exe"
        if sys.platform == "win32"
        else "launchctl"
        if sys.platform == "darwin"
        else "systemctl"
        if sys.platform.startswith("linux")
        else ""
    )
    scheduler_present = bool(scheduler_command and shutil.which(scheduler_command))
    checks.append(
        (
            "Scheduler",
            scheduler_present,
            f"native scheduler available ({scheduler_command})"
            if scheduler_present
            else "native scheduler command is unavailable",
        )
    )
    checks.append(("Data directory", True, str(paths.data_dir)))

    failed = False
    for name, passed, detail in checks:
        failed = failed or not passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    return 1 if failed else 0


def _playwright_browser_check(browser_channel: str) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            if browser_channel == "chromium":
                browser = playwright.chromium.launch(headless=True)
            else:
                browser = playwright.chromium.launch(
                    channel=browser_channel,
                    headless=True,
                )
            version = browser.version
            browser.close()
        return True, f"launch succeeded (version {version})"
    except Exception as error:
        hint = (
            "run 'playwright install chromium'"
            if browser_channel == "chromium"
            else f"install {browser_channel} or select another browser_channel"
        )
        return False, f"launch failed ({type(error).__name__}); {hint}"


def _login(
    config_path: Path,
    paths: ProfilePaths,
    profile_name: str,
) -> int:
    config = load_config(config_path, require_resume=False)
    if not sys.stdin.isatty():
        raise ConfigurationError("interactive login requires a terminal")
    paths.ensure_runtime_dirs()
    try:
        with RunLock(paths.run_lock), BrowserSession(
            paths.browser_profile,
            browser_channel=config.browser_channel,
            headless=False,
            timeout_seconds=config.timeout_seconds,
        ) as session:
            site = NaukriSite(session.page, timeout_seconds=config.timeout_seconds)
            site.open_login()
            initial_state = site.wait_for_auth_state()
            if initial_state == AuthState.AUTHENTICATED:
                print("Already authenticated; the dedicated browser profile is ready.")
                return 0
            if initial_state == AuthState.LOGIN_REQUIRED:
                password = CredentialStore().get(profile_name)
                if not password:
                    print(
                        "No stored password is available. Run: naukri-auto credentials update "
                        f"--profile {profile_name}"
                    )
                    return 3
                if site.fill_login(config.username, password):
                    if not site.submit_login():
                        LOGGER.warning("login button was not found for profile %s", profile_name)
                        print("The login button was not found; the site contract may have changed.")
                        return 3
                    result = site.wait_for_login_result()
                    if result == AuthState.AUTHENTICATED:
                        LOGGER.info("login succeeded for profile %s", profile_name)
                        print("Login confirmed; the dedicated browser profile is ready.")
                        return 0
                    if result == AuthState.INVALID_CREDENTIALS:
                        LOGGER.warning(
                            "Naukri rejected stored login credentials for profile %s",
                            profile_name,
                        )
                        print("Naukri rejected the stored email or password.")
                        print(
                            "Update password: naukri-auto credentials update "
                            f"--profile {profile_name}"
                        )
                        print(
                            "Update email: naukri-auto profile edit "
                            f"{profile_name} --username <login>"
                        )
                        print(f"Log: {paths.logs / 'naukri-auto.log'}")
                        return 3
                    if result == AuthState.CHALLENGE_REQUIRED:
                        LOGGER.info("manual login challenge required for profile %s", profile_name)
                        print("Complete CAPTCHA or MFA manually in the browser.")
                        input("Press Enter after the profile is visible...")
                    else:
                        LOGGER.warning(
                            "login outcome was not identified for profile %s", profile_name
                        )
                        print(
                            "Login did not reach a recognized result before the timeout; "
                            "inspect the browser and local log."
                        )
                        print(f"Log: {paths.logs / 'naukri-auto.log'}")
                        _capture_login_failure(session, paths)
                        return 3
                else:
                    LOGGER.warning("login fields were not identified for profile %s", profile_name)
                    print(
                        "The login fields were not identified; the site contract may have changed."
                    )
                    _capture_login_failure(session, paths)
                    return 3
            elif initial_state == AuthState.CHALLENGE_REQUIRED:
                print("Complete CAPTCHA or MFA manually in the browser.")
                input("Press Enter after the profile is visible...")
            elif initial_state == AuthState.INVALID_CREDENTIALS:
                print("Naukri is already showing an invalid-credential error.")
                print(
                    "Update password: naukri-auto credentials update "
                    f"--profile {profile_name}"
                )
                return 3
            else:
                LOGGER.warning("initial login page was not identified for profile %s", profile_name)
                print("Could not identify the Naukri login page; stopping safely.")
                _capture_login_failure(session, paths)
                return 3
            if session.page.is_closed():
                print(
                    "Browser was closed before login verification. "
                    "The session may have been saved; run the headed dry run to confirm it."
                )
                return 3
            try:
                site.open_profile()
                state = site.wait_for_auth_state()
            except Exception as error:
                if type(error).__name__ == "TargetClosedError":
                    print(
                        "Browser was closed before login verification. "
                        "The session may have been saved; run the headed dry run to confirm it."
                    )
                    return 3
                raise
            if state != AuthState.AUTHENTICATED:
                print(
                    "Login was not confirmed. "
                    "The browser profile was retained for another attempt."
                )
                return 3
    except AlreadyRunningError as error:
        raise ConfigurationError("another login or automation run is active") from error
    print("Login confirmed; the dedicated browser profile is ready.")
    return 0


def _capture_login_failure(session: BrowserSession, paths: ProfilePaths) -> None:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = paths.artifacts / f"login-{timestamp}"
    session.capture_failure(artifact_dir)
    print(f"Artifacts: {artifact_dir}")
    print(f"Log: {paths.logs / 'naukri-auto.log'}")


def _configure_logging(paths: AppPaths | ProfilePaths, *, verbose: bool) -> None:
    paths.logs.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        paths.logs / "naukri-auto.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        handlers=[handler],
    )
if __name__ == "__main__":
    raise SystemExit(main())
