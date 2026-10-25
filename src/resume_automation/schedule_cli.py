from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from resume_automation.config import (
    ConfigurationError,
    ScheduleConfig,
    ScheduleRule,
    load_config,
    write_config,
)
from resume_automation.paths import ProfilePaths
from resume_automation.scheduling import scheduler_for_profile


def add_schedule_parser(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    schedule = commands.add_parser("schedule", help="configure and manage the native scheduler")
    schedule_commands = schedule.add_subparsers(dest="schedule_command", required=True)
    for name in ("set", "add"):
        command = schedule_commands.add_parser(name)
        command.add_argument("--profile")
        command.add_argument("--times", required=True, help="comma-separated HH:MM times")
        command.add_argument("--days", help="comma-separated MON,TUE,...; omit for every day")
    install = schedule_commands.add_parser("install")
    install.add_argument("--profile")
    install.add_argument("--yes", action="store_true", help="skip confirmation")
    for name in ("list", "run-now", "remove"):
        command = schedule_commands.add_parser(name)
        command.add_argument("--profile")
    show = schedule_commands.add_parser("show")
    show.add_argument("--profile")
    show.add_argument("--verbose", action="store_true", dest="schedule_verbose")


def handle_schedule(
    args: argparse.Namespace,
    config_path: Path,
    paths: ProfilePaths,
    profile_name: str,
    *,
    python_executable: Path,
) -> int:
    if args.schedule_command in {"run-now", "remove"}:
        scheduler = scheduler_for_profile(profile_name)
        output = scheduler.run_now() if args.schedule_command == "run-now" else scheduler.remove()
        print(output)
        return 0

    config = load_config(config_path)
    if args.schedule_command == "show":
        scheduler = scheduler_for_profile(profile_name)
        if args.schedule_verbose:
            print(scheduler.show(verbose=True))
        else:
            print(f"Profile: {profile_name}")
            print(f"Schedule: {schedule_summary(config.schedule)}")
            print(scheduler.show())
        return 0
    if args.schedule_command in {"set", "add"}:
        rule = _schedule_rule(args.times, args.days)
        rules = (rule,) if args.schedule_command == "set" else (*config.schedule.rules, rule)
        updated = replace(config, schedule=replace(config.schedule, rules=rules))
        write_config(updated, config_path)
        print(schedule_summary(updated.schedule))
        return 0
    if args.schedule_command == "list":
        print(schedule_summary(config.schedule))
        return 0

    scheduler = scheduler_for_profile(profile_name)
    print(f"Install schedule: {schedule_summary(config.schedule)}")
    if not args.yes and not _prompt_yes_no("Continue", False):
        print("Schedule installation cancelled.")
        return 1
    print(
        scheduler.install_schedule(
            config.schedule,
            python_executable=python_executable,
            working_directory=paths.config_dir,
            data_directory=paths.data_dir,
            profile_name=profile_name,
        )
    )
    return 0


def schedule_summary(schedule: ScheduleConfig) -> str:
    return "; ".join(
        f"{','.join(rule.days) if rule.days else 'every day'} at {','.join(rule.times)}"
        for rule in schedule.rules
    )


def _schedule_rule(times_value: str, days_value: str | None) -> ScheduleRule:
    times = tuple(value.strip() for value in times_value.split(",") if value.strip())
    days = tuple(
        value.strip().upper() for value in (days_value or "").split(",") if value.strip()
    )
    return ScheduleRule(times=times, days=days)


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
