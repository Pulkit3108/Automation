from __future__ import annotations

import argparse
import importlib.util
import logging
import logging.handlers
import shutil
import sys
from pathlib import Path

from naukri_automation import __version__
from naukri_automation.browser_session import BrowserDependencyError, BrowserSession
from naukri_automation.config import (
    DAY_NAMES,
    AppConfig,
    ConfigurationError,
    NotificationConfig,
    ScheduleConfig,
    load_config,
    resolve_config_path,
    write_config,
)
from naukri_automation.naukri_site import AuthState, LOGIN_URL, NaukriSite
from naukri_automation.paths import AppPaths, get_app_paths
from naukri_automation.scheduling.windows import (
    SchedulerError,
    WindowsScheduler,
    build_task_xml,
)
from naukri_automation.run_lock import AlreadyRunningError, RunLock
from naukri_automation.workflow import execute

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="naukri-auto",
        description="Safely update a Naukri resume from a scheduled one-shot command.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, help="override the platform config.toml path")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("configure", help="create or replace local non-secret configuration")
    commands.add_parser("doctor", help="run side-effect-free local readiness checks")
    login = commands.add_parser("login", help="open a headed browser for interactive Naukri login")
    login.add_argument("--headed", action="store_true", help=argparse.SUPPRESS)

    run = commands.add_parser("run", help="perform one resume-update workflow")
    run.add_argument("--dry-run", action="store_true", help="stop before selecting a file")
    run.add_argument("--headed", action="store_true", help="show the browser window")

    schedule = commands.add_parser("schedule", help="manage the Windows scheduled task")
    schedule_commands = schedule.add_subparsers(dest="schedule_command", required=True)
    install = schedule_commands.add_parser("install")
    install.add_argument("--yes", action="store_true", help="skip confirmation")
    schedule_commands.add_parser("show")
    schedule_commands.add_parser("run-now")
    schedule_commands.add_parser("remove")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = get_app_paths()
    _configure_logging(paths, verbose=args.verbose)
    config_path = resolve_config_path(args.config)

    try:
        if args.command == "configure":
            return _configure(config_path)
        if args.command == "doctor":
            return _doctor(config_path, paths)
        if args.command == "login":
            return _login(config_path, paths)
        if args.command == "run":
            config = load_config(config_path)
            result = execute(
                config,
                paths,
                dry_run=args.dry_run,
                headed=args.headed,
            )
            print(f"{result.outcome.value}: {result.message}")
            if result.artifact_dir:
                print(f"Artifacts: {result.artifact_dir}")
            return result.exit_code
        if args.command == "schedule":
            return _schedule(args, config_path, paths)
    except (ConfigurationError, SchedulerError, BrowserDependencyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    return 2


def _configure(config_path: Path) -> int:
    print("No credentials, cookies, or resume contents are written to this configuration.")
    resume = Path(_prompt("Absolute resume path"))
    schedule_frequency = _prompt("Schedule frequency (daily/weekly)", "daily").lower()
    schedule_time = _prompt("Local run time (HH:MM)", "09:00")
    days: tuple[str, ...] = ()
    if schedule_frequency == "weekly":
        raw_days = _prompt("Days (comma-separated MON,TUE,...)", "MON")
        days = tuple(day.strip().upper() for day in raw_days.split(",") if day.strip())
    headless = _prompt_yes_no("Run scheduled browser headlessly", True)
    notification_enabled = _prompt_yes_no("Enable ntfy-compatible notifications", False)
    base_url = "https://ntfy.sh"
    topic = ""
    if notification_enabled:
        base_url = _prompt("Notification base URL", base_url)
        topic = _prompt("Notification topic")

    config = AppConfig(
        resume_path=resume,
        headless=headless,
        notification=NotificationConfig(
            enabled=notification_enabled,
            base_url=base_url,
            topic=topic,
        ),
        schedule=ScheduleConfig(
            frequency=schedule_frequency,
            time=schedule_time,
            days=days,
        ),
    )
    config.validate(require_resume=True)
    written = write_config(config, config_path)
    print(f"Configuration written to {written}")
    return 0


def _doctor(config_path: Path, paths: AppPaths) -> int:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python", sys.version_info >= (3, 12), sys.version.split()[0]))
    checks.append(("Configuration", config_path.is_file(), str(config_path)))
    try:
        config = load_config(config_path)
        checks.append(("Configuration schema", True, "valid"))
        checks.append(("Resume", True, f"{config.resume_path.name} is readable"))
    except ConfigurationError as error:
        checks.append(("Configuration schema", False, str(error)))
    playwright_present = importlib.util.find_spec("playwright") is not None
    checks.append(
        (
            "Playwright package",
            playwright_present,
            "installed" if playwright_present else "install project dependencies",
        )
    )
    scheduler_present = sys.platform != "win32" or shutil.which("schtasks.exe") is not None
    checks.append(
        (
            "Scheduler",
            scheduler_present,
            "Windows Task Scheduler available"
            if sys.platform == "win32" and scheduler_present
            else "manual runs supported; schedule installation is Windows-only",
        )
    )
    checks.append(("Data directory", True, str(paths.data_dir)))

    failed = False
    for name, passed, detail in checks:
        failed = failed or not passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    if playwright_present:
        print("[INFO] Browser check: run 'playwright install chromium' after installation")
    return 1 if failed else 0


def _login(config_path: Path, paths: AppPaths) -> int:
    config = load_config(config_path, require_resume=False)
    if not sys.stdin.isatty():
        raise ConfigurationError("interactive login requires a terminal")
    paths.ensure_runtime_dirs()
    try:
        with RunLock(paths.run_lock):
            with BrowserSession(
                paths.browser_profile,
                headless=False,
                timeout_seconds=config.timeout_seconds,
            ) as session:
                session.page.goto(LOGIN_URL, wait_until="domcontentloaded")
                print(
                    "Complete Naukri login in the browser. "
                    "CAPTCHA and MFA must be completed manually."
                )
                input("Press Enter after the profile is visible...")
                site = NaukriSite(session.page, timeout_seconds=config.timeout_seconds)
                site.open_profile()
                if site.auth_state() != AuthState.AUTHENTICATED:
                    print(
                        "Login was not confirmed. "
                        "The browser profile was retained for another attempt."
                    )
                    return 3
    except AlreadyRunningError as error:
        raise ConfigurationError("another login or automation run is active") from error
    print("Login confirmed; the dedicated browser profile is ready.")
    return 0


def _schedule(args: argparse.Namespace, config_path: Path, paths: AppPaths) -> int:
    scheduler = WindowsScheduler()
    if args.schedule_command == "show":
        print(scheduler.show())
        return 0
    if args.schedule_command == "run-now":
        print(scheduler.run_now())
        return 0
    if args.schedule_command == "remove":
        print(scheduler.remove())
        return 0

    config = load_config(config_path)
    task_xml = build_task_xml(
        config.schedule,
        python_executable=Path(sys.executable),
        config_path=config_path,
    )
    print(
        f"Install Windows task at {config.schedule.time} ({config.schedule.frequency}, local time)"
    )
    if not args.yes and not _prompt_yes_no("Continue", False):
        print("Schedule installation cancelled.")
        return 1
    print(scheduler.install(task_xml, paths.data_dir / "task.xml"))
    return 0


def _configure_logging(paths: AppPaths, *, verbose: bool) -> None:
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


def _prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ConfigurationError(f"{label} is required")


def _prompt_yes_no(label: str, default: bool) -> bool:
    default_text = "Y/n" if default else "y/N"
    value = input(f"{label} [{default_text}]: ").strip().lower()
    if not value:
        return default
    if value in {"y", "yes"}:
        return True
    if value in {"n", "no"}:
        return False
    raise ConfigurationError(f"invalid yes/no response for {label}")


if __name__ == "__main__":
    raise SystemExit(main())
