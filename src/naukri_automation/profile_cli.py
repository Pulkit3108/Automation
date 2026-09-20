from __future__ import annotations

import argparse
import getpass
import sys
from dataclasses import replace
from pathlib import Path

from naukri_automation.config import AppConfig, ConfigurationError
from naukri_automation.credentials import CredentialStore
from naukri_automation.paths import AppPaths, ProfilePaths
from naukri_automation.profile_store import (
    create_profile,
    import_resume,
    list_profiles,
    list_resumes,
    load_profile,
    read_last_result,
    remove_resume,
    resolve_profile_name,
    select_resume,
    set_default_profile,
    update_profile,
)
from naukri_automation.scheduling.windows import WindowsScheduler


def add_management_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    profile = commands.add_parser("profile", help="manage automation profiles")
    profile_commands = profile.add_subparsers(dest="profile_command", required=True)
    create = profile_commands.add_parser("create")
    create.add_argument("name")
    create.add_argument("--username")
    create.add_argument("--resume", type=Path)
    profile_commands.add_parser("list")
    show = profile_commands.add_parser("show")
    show.add_argument("name")
    edit = profile_commands.add_parser("edit")
    edit.add_argument("name")
    edit.add_argument("--username")
    edit.add_argument("--browser-channel", choices=("chrome", "chromium", "msedge"))
    edit.add_argument("--schedule-frequency", choices=("daily", "weekly"))
    edit.add_argument("--schedule-time")
    edit.add_argument("--schedule-days", help="comma-separated MON,TUE,...")
    headless = edit.add_mutually_exclusive_group()
    headless.add_argument("--headless", action="store_true", dest="headless")
    headless.add_argument("--headed", action="store_false", dest="headless")
    edit.set_defaults(headless=None)
    default = profile_commands.add_parser("default")
    default.add_argument("name")

    credentials = commands.add_parser("credentials", help="manage OS-keyring credentials")
    credential_commands = credentials.add_subparsers(
        dest="credentials_command", required=True
    )
    for name in ("update", "remove", "status"):
        command = credential_commands.add_parser(name)
        command.add_argument("--profile")

    resume = commands.add_parser("resume", help="manage profile résumés")
    resume_commands = resume.add_subparsers(dest="resume_command", required=True)
    add = resume_commands.add_parser("add")
    add.add_argument("source", type=Path)
    add.add_argument("--profile")
    add.add_argument("--replace", action="store_true")
    add.add_argument("--select", action="store_true")
    listing = resume_commands.add_parser("list")
    listing.add_argument("--profile")
    select = resume_commands.add_parser("select")
    select.add_argument("filename")
    select.add_argument("--profile")
    remove = resume_commands.add_parser("remove")
    remove.add_argument("filename")
    remove.add_argument("--profile")


def handle_management_command(args: argparse.Namespace, paths: AppPaths) -> int:
    if args.command == "profile":
        return _profile_command(args, paths)

    profile_name = resolve_profile_name(paths, args.profile)
    if args.command == "credentials":
        return _credentials_command(args, profile_name)
    return _resume_command(args, paths, profile_name)


def _profile_command(args: argparse.Namespace, paths: AppPaths) -> int:
    if args.profile_command == "list":
        profiles = list_profiles(paths)
        default = _read_default_profile(paths)
        if not profiles:
            print("No profiles configured.")
            return 0
        for name in profiles:
            marker = "*" if name == default else " "
            config = load_profile(paths, name, require_resume=False)
            print(f"{marker} {name}: {config.username} ({config.resume_path.name})")
        return 0

    if args.profile_command == "default":
        name = set_default_profile(paths, args.name)
        print(f"Default profile: {name}")
        return 0

    if args.profile_command == "create":
        username = args.username or _prompt("Naukri username")
        resume = args.resume or Path(_prompt("Résumé path"))
        password = getpass.getpass("Naukri password (stored in OS keyring): ")
        if not password:
            raise ConfigurationError("password cannot be empty")
        config, profile_paths = create_profile(
            paths,
            name=args.name,
            username=username,
            resume_source=resume,
        )
        try:
            CredentialStore().set(config.profile_name, password)
        except ConfigurationError as error:
            raise ConfigurationError(
                f"profile {config.profile_name} was created, but its credential was not stored; "
                "run 'naukri-auto credentials update' after fixing the OS keyring"
            ) from error
        if len(list_profiles(paths)) == 1:
            set_default_profile(paths, config.profile_name)
        print(f"Profile created: {config.profile_name}")
        print(f"Managed résumé: {profile_paths.resumes / config.resume_path.name}")
        return 0

    name = resolve_profile_name(paths, args.name)
    profile_paths = paths.profile(name)
    config = load_profile(paths, name, require_resume=False)
    if args.profile_command == "show":
        return _show_profile(config, profile_paths)

    changes: dict[str, object] = {}
    if args.username is not None:
        changes["username"] = args.username.strip()
    if args.browser_channel is not None:
        changes["browser_channel"] = args.browser_channel
    if args.headless is not None:
        changes["headless"] = args.headless

    if any(
        value is not None
        for value in (args.schedule_frequency, args.schedule_time, args.schedule_days)
    ):
        days = config.schedule.days
        if args.schedule_days is not None:
            days = tuple(
                day.strip().upper()
                for day in args.schedule_days.split(",")
                if day.strip()
            )
        changes["schedule"] = replace(
            config.schedule,
            frequency=args.schedule_frequency or config.schedule.frequency,
            time=args.schedule_time or config.schedule.time,
            days=days,
        )
    if not changes:
        raise ConfigurationError("no profile changes were supplied")
    updated = update_profile(config, profile_paths, **changes)
    print(f"Profile updated: {updated.profile_name}")
    return 0


def _show_profile(config: AppConfig, paths: ProfilePaths) -> int:
    try:
        credentials = "yes" if CredentialStore().has(config.profile_name) else "no"
    except ConfigurationError:
        credentials = "unavailable"
    last_result = read_last_result(paths)
    outcome = str(last_result.get("outcome", "unknown")) if last_result else "never run"
    timestamp = str(last_result.get("timestamp_utc", "")) if last_result else ""
    scheduled = _schedule_state(config.profile_name)

    print(f"Profile:             {config.profile_name}")
    print(f"Naukri username:     {config.username}")
    print(f"Credentials stored:  {credentials}")
    print(f"Active résumé:       {config.resume_path.name}")
    print(f"Résumé path:         {config.resume_path}")
    print(f"Browser channel:     {config.browser_channel}")
    print(f"Schedule configured: {config.schedule.frequency} at {config.schedule.time}")
    print(f"Scheduled task:      {scheduled}")
    print(f"Last result:         {outcome}{f' at {timestamp}' if timestamp else ''}")
    return 0


def _credentials_command(args: argparse.Namespace, profile_name: str) -> int:
    store = CredentialStore()
    if args.credentials_command == "status":
        print("stored" if store.has(profile_name) else "not stored")
        return 0
    if args.credentials_command == "remove":
        removed = store.remove(profile_name)
        print("Credential removed." if removed else "No credential was stored.")
        return 0
    password = getpass.getpass("New Naukri password (stored in OS keyring): ")
    store.set(profile_name, password)
    print("Credential updated.")
    return 0


def _resume_command(args: argparse.Namespace, paths: AppPaths, profile_name: str) -> int:
    profile_paths = paths.profile(profile_name)
    config = load_profile(paths, profile_name, require_resume=False)
    if args.resume_command == "list":
        resumes = list_resumes(profile_paths)
        if not resumes:
            print("No managed résumés.")
            return 0
        active = config.resume_path.resolve()
        for resume in resumes:
            marker = "*" if resume.resolve() == active else " "
            print(f"{marker} {resume.name}")
        return 0
    if args.resume_command == "add":
        managed = import_resume(
            profile_paths,
            args.source,
            replace_existing=args.replace,
            max_resume_mb=config.max_resume_mb,
        )
        if args.select:
            select_resume(config, profile_paths, managed.name)
        print(f"Résumé imported: {managed.name}")
        if args.select:
            print("Active résumé updated.")
        return 0
    if args.resume_command == "select":
        selected = select_resume(config, profile_paths, args.filename)
        print(f"Active résumé: {selected.resume_path.name}")
        return 0
    remove_resume(config, profile_paths, args.filename)
    print(f"Résumé removed: {args.filename}")
    return 0


def _schedule_state(profile_name: str) -> str:
    if sys.platform != "win32":
        return "not checked (Windows only)"
    scheduler = WindowsScheduler(task_name=f"NaukriResumeAutomation-{profile_name}")
    return "installed" if scheduler.is_installed() else "not installed"


def _read_default_profile(paths: AppPaths) -> str | None:
    try:
        return paths.default_profile_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _prompt(label: str) -> str:
    value = input(f"{label}: ").strip()
    if not value:
        raise ConfigurationError(f"{label} is required")
    return value
