from __future__ import annotations

import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

from naukri_automation.config import (
    ALLOWED_RESUME_SUFFIXES,
    AppConfig,
    ConfigurationError,
    load_config,
    write_config,
)
from naukri_automation.paths import AppPaths, ProfilePaths

PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_profile_name(name: str) -> str:
    normalized = name.strip().lower()
    if not normalized or not PROFILE_NAME_PATTERN.fullmatch(normalized):
        raise ConfigurationError(
            "profile name may contain only letters, numbers, _ and -"
        )
    return normalized


def list_profiles(paths: AppPaths) -> list[str]:
    if not paths.profiles_config_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in paths.profiles_config_dir.iterdir()
        if child.is_dir() and (child / "profile.toml").is_file()
    )


def resolve_profile_name(paths: AppPaths, requested: str | None) -> str:
    if requested:
        name = validate_profile_name(requested)
        if not paths.profile(name).config_file.is_file():
            raise ConfigurationError(f"profile does not exist: {name}")
        return name

    if paths.default_profile_file.is_file():
        name = validate_profile_name(
            paths.default_profile_file.read_text(encoding="utf-8").strip()
        )
        if paths.profile(name).config_file.is_file():
            return name

    profiles = list_profiles(paths)
    if len(profiles) == 1:
        return profiles[0]
    if not profiles:
        raise ConfigurationError("no profiles exist; run 'naukri-auto profile create'")
    raise ConfigurationError("multiple profiles exist; specify --profile or set a default")


def load_profile(paths: AppPaths, name: str, *, require_resume: bool = True) -> AppConfig:
    normalized = validate_profile_name(name)
    return load_config(paths.profile(normalized).config_file, require_resume=require_resume)


def create_profile(
    paths: AppPaths,
    *,
    name: str,
    username: str,
    resume_source: Path,
) -> tuple[AppConfig, ProfilePaths]:
    normalized = validate_profile_name(name)
    profile_paths = paths.profile(normalized)
    if profile_paths.config_file.exists():
        raise ConfigurationError(f"profile already exists: {normalized}")
    if not username.strip():
        raise ConfigurationError("Naukri username is required")

    profile_paths.ensure_runtime_dirs()
    managed_resume = import_resume(profile_paths, resume_source)
    config = AppConfig(
        profile_name=normalized,
        username=username.strip(),
        resume_path=managed_resume,
    )
    config.validate(require_resume=True)
    write_config(config, profile_paths.config_file)
    return config, profile_paths


def update_profile(config: AppConfig, profile_paths: ProfilePaths, **changes: object) -> AppConfig:
    updated = replace(config, **changes)
    updated.validate(require_resume=True)
    write_config(updated, profile_paths.config_file)
    return updated


def set_default_profile(paths: AppPaths, name: str) -> str:
    normalized = resolve_profile_name(paths, name)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    temporary = paths.default_profile_file.with_suffix(".tmp")
    temporary.write_text(normalized + "\n", encoding="utf-8")
    temporary.replace(paths.default_profile_file)
    return normalized


def import_resume(
    profile_paths: ProfilePaths,
    source: Path,
    *,
    replace_existing: bool = False,
    max_resume_mb: int = 5,
) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ConfigurationError(f"resume file does not exist: {source}")
    if source.suffix.lower() not in ALLOWED_RESUME_SUFFIXES:
        raise ConfigurationError("resume must end in .pdf, .doc, or .docx")
    if source.stat().st_size == 0:
        raise ConfigurationError("resume file is empty")
    if source.stat().st_size > max_resume_mb * 1024 * 1024:
        raise ConfigurationError(f"resume exceeds configured limit of {max_resume_mb} MB")

    profile_paths.resumes.mkdir(parents=True, exist_ok=True)
    destination = profile_paths.resumes / source.name
    if destination.exists() and not replace_existing:
        raise ConfigurationError(
            f"resume already exists: {source.name}; use --replace to overwrite it"
        )
    shutil.copy2(source, destination)
    return destination


def list_resumes(profile_paths: ProfilePaths) -> list[Path]:
    if not profile_paths.resumes.is_dir():
        return []
    return sorted(
        path
        for path in profile_paths.resumes.iterdir()
        if path.is_file() and path.suffix.lower() in ALLOWED_RESUME_SUFFIXES
    )


def select_resume(config: AppConfig, profile_paths: ProfilePaths, filename: str) -> AppConfig:
    if Path(filename).name != filename:
        raise ConfigurationError("resume selection must be a filename, not a path")
    candidate = profile_paths.resumes / filename
    if not candidate.is_file():
        raise ConfigurationError(f"managed resume does not exist: {filename}")
    return update_profile(config, profile_paths, resume_path=candidate)


def remove_resume(config: AppConfig, profile_paths: ProfilePaths, filename: str) -> None:
    if Path(filename).name != filename:
        raise ConfigurationError("resume removal must use a filename, not a path")
    candidate = profile_paths.resumes / filename
    if candidate.resolve() == config.resume_path.resolve():
        raise ConfigurationError("cannot remove the active resume; select another first")
    if not candidate.is_file():
        raise ConfigurationError(f"managed resume does not exist: {filename}")
    candidate.unlink()


def read_last_result(profile_paths: ProfilePaths) -> dict[str, object] | None:
    try:
        payload = json.loads(profile_paths.last_result.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None
