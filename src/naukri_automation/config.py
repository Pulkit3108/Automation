from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from naukri_automation.paths import get_app_paths

ALLOWED_RESUME_SUFFIXES = {".pdf", ".doc", ".docx"}
DAY_NAMES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
TOPIC_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
SUPPORTED_BROWSER_CHANNELS = {"chrome", "chromium", "msedge"}
MAX_SCHEDULE_TRIGGERS = 48


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class NotificationConfig:
    enabled: bool = False
    base_url: str = "https://ntfy.sh"
    topic: str = ""


@dataclass(frozen=True)
class ScheduleRule:
    times: tuple[str, ...] = ("09:00",)
    days: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScheduleConfig:
    rules: tuple[ScheduleRule, ...] = (ScheduleRule(),)
    wake_computer: bool = True


@dataclass(frozen=True)
class AppConfig:
    resume_path: Path
    profile_name: str = "default"
    username: str = "unknown"
    browser_channel: str = "chrome"
    headless: bool = True
    timeout_seconds: int = 45
    artifact_retention_days: int = 14
    max_resume_mb: int = 5
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)

    def validate(self, *, require_resume: bool = True) -> None:
        errors: list[str] = []
        resume = self.resume_path.expanduser()

        if not TOPIC_PATTERN.fullmatch(self.profile_name):
            errors.append("profile_name may contain only letters, numbers, _ and -")
        if not self.username.strip() or len(self.username) > 254:
            errors.append("username must contain between 1 and 254 characters")
        if not resume.is_absolute():
            errors.append("resume_path must be absolute")
        if resume.suffix.lower() not in ALLOWED_RESUME_SUFFIXES:
            errors.append("resume_path must end in .pdf, .doc, or .docx")
        if require_resume and not resume.is_file():
            errors.append(f"resume file does not exist: {resume}")
        if require_resume and resume.is_file():
            size = resume.stat().st_size
            if size == 0:
                errors.append("resume file is empty")
            if size > self.max_resume_mb * 1024 * 1024:
                errors.append(f"resume exceeds configured limit of {self.max_resume_mb} MB")

        if not 10 <= self.timeout_seconds <= 300:
            errors.append("timeout_seconds must be between 10 and 300")
        if self.browser_channel not in SUPPORTED_BROWSER_CHANNELS:
            errors.append("browser_channel must be chrome, chromium, or msedge")
        if not 1 <= self.artifact_retention_days <= 90:
            errors.append("artifact_retention_days must be between 1 and 90")
        if not 1 <= self.max_resume_mb <= 20:
            errors.append("max_resume_mb must be between 1 and 20")

        if not self.schedule.rules:
            errors.append("schedule requires at least one rule")
        trigger_count = 0
        occurrences: set[tuple[str, str]] = set()
        for rule in self.schedule.rules:
            if not rule.times:
                errors.append("each schedule rule requires at least one time")
            invalid_times = [
                value
                for value in rule.times
                if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value)
            ]
            if invalid_times:
                errors.append("schedule times must use 24-hour HH:MM format")
            if len(set(rule.times)) != len(rule.times):
                errors.append("schedule rule times must not contain duplicates")
            invalid_days = sorted(set(rule.days) - set(DAY_NAMES))
            if invalid_days:
                errors.append(f"invalid schedule days: {', '.join(invalid_days)}")
            active_days = rule.days or DAY_NAMES
            for value in rule.times:
                trigger_count += 1
                for day in active_days:
                    occurrence = (day, value)
                    if occurrence in occurrences:
                        errors.append(f"duplicate schedule occurrence: {day} at {value}")
                    occurrences.add(occurrence)
        if trigger_count > MAX_SCHEDULE_TRIGGERS:
            errors.append(
                f"schedule supports at most {MAX_SCHEDULE_TRIGGERS} native triggers"
            )

        if self.notification.enabled:
            if not self.notification.base_url.startswith("https://"):
                errors.append("notification.base_url must use https")
            if not TOPIC_PATTERN.fullmatch(self.notification.topic):
                errors.append("notification.topic may contain only letters, numbers, _ and -")

        if errors:
            raise ConfigurationError("; ".join(errors))


def resolve_config_path(path: Path | None = None) -> Path:
    return path.expanduser() if path else get_app_paths().config_file


def load_config(path: Path | None = None, *, require_resume: bool = True) -> AppConfig:
    config_path = resolve_config_path(path)
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigurationError(
            f"configuration not found: {config_path}; run 'naukri-auto profile create'"
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"invalid TOML in {config_path}: {error}") from error

    notification = _table(raw, "notification")
    schedule = _table(raw, "schedule")
    schedule_rules = _table_list(schedule, "rules")
    config = AppConfig(
        resume_path=Path(_string(raw, "resume_path")).expanduser(),
        profile_name=_string(raw, "profile_name", "default"),
        username=_string(raw, "username", "unknown"),
        browser_channel=_string(raw, "browser_channel", "chrome").lower(),
        headless=_boolean(raw, "headless", True),
        timeout_seconds=_integer(raw, "timeout_seconds", 45),
        artifact_retention_days=_integer(raw, "artifact_retention_days", 14),
        max_resume_mb=_integer(raw, "max_resume_mb", 5),
        notification=NotificationConfig(
            enabled=_boolean(notification, "enabled", False),
            base_url=_string(notification, "base_url", "https://ntfy.sh"),
            topic=_string(notification, "topic", ""),
        ),
        schedule=ScheduleConfig(
            rules=tuple(
                ScheduleRule(
                    times=tuple(_string_list(rule, "times", [])),
                    days=tuple(day.upper() for day in _string_list(rule, "days", [])),
                )
                for rule in schedule_rules
            ),
            wake_computer=_boolean(schedule, "wake_computer", True),
        ),
    )
    config.validate(require_resume=require_resume)
    return config


def write_config(config: AppConfig, path: Path | None = None) -> Path:
    config.validate(require_resume=False)
    config_path = resolve_config_path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(render_config(config), encoding="utf-8")
    return config_path


def render_config(config: AppConfig) -> str:
    lines = [
        f"profile_name = {_toml_string(config.profile_name)}",
        f"username = {_toml_string(config.username)}",
        f"resume_path = {_toml_string(str(config.resume_path.expanduser()))}",
        f"browser_channel = {_toml_string(config.browser_channel)}",
        f"headless = {str(config.headless).lower()}",
        f"timeout_seconds = {config.timeout_seconds}",
        f"artifact_retention_days = {config.artifact_retention_days}",
        f"max_resume_mb = {config.max_resume_mb}",
        "",
        "[notification]",
        f"enabled = {str(config.notification.enabled).lower()}",
        f"base_url = {_toml_string(config.notification.base_url)}",
        f"topic = {_toml_string(config.notification.topic)}",
        "",
        "[schedule]",
        f"wake_computer = {str(config.schedule.wake_computer).lower()}",
    ]
    for rule in config.schedule.rules:
        days = ", ".join(_toml_string(day) for day in rule.days)
        times = ", ".join(_toml_string(value) for value in rule.times)
        lines.extend(
            [
                "",
                "[[schedule.rules]]",
                f"days = [{days}]",
                f"times = [{times}]",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} must be a TOML table")
    return value


def _string(raw: dict[str, Any], key: str, default: str | None = None) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise ConfigurationError(f"{key} must be a string")
    return value


def _integer(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{key} must be an integer")
    return value


def _boolean(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{key} must be true or false")
    return value


def _string_list(raw: dict[str, Any], key: str, default: list[str]) -> list[str]:
    value = raw.get(key, default)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigurationError(f"{key} must be a list of strings")
    return value


def _table_list(raw: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = raw.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ConfigurationError(f"{key} must be a list of TOML tables")
    return value
