from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "NaukriAutomation"


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    data_dir: Path

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.toml"

    @property
    def profiles_config_dir(self) -> Path:
        return self.config_dir / "profiles"

    @property
    def profiles_data_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def default_profile_file(self) -> Path:
        return self.config_dir / "default-profile"

    @property
    def browser_profile(self) -> Path:
        return self.data_dir / "browser-profile"

    @property
    def logs(self) -> Path:
        return self.data_dir / "logs"

    @property
    def artifacts(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def run_lock(self) -> Path:
        return self.data_dir / "run.lock"

    @property
    def last_result(self) -> Path:
        return self.data_dir / "last-result.json"

    def ensure_runtime_dirs(self) -> None:
        for path in (self.config_dir, self.data_dir, self.logs, self.artifacts):
            path.mkdir(parents=True, exist_ok=True)

    def profile(self, name: str) -> ProfilePaths:
        return ProfilePaths(
            name=name,
            config_dir=self.profiles_config_dir / name,
            data_dir=self.profiles_data_dir / name,
        )


@dataclass(frozen=True)
class ProfilePaths:
    name: str
    config_dir: Path
    data_dir: Path

    @property
    def config_file(self) -> Path:
        return self.config_dir / "profile.toml"

    @property
    def resumes(self) -> Path:
        return self.data_dir / "resumes"

    @property
    def browser_profile(self) -> Path:
        return self.data_dir / "browser-profile"

    @property
    def logs(self) -> Path:
        return self.data_dir / "logs"

    @property
    def artifacts(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def run_lock(self) -> Path:
        return self.data_dir / "run.lock"

    @property
    def last_result(self) -> Path:
        return self.data_dir / "last-result.json"

    def ensure_runtime_dirs(self) -> None:
        for path in (
            self.config_dir,
            self.data_dir,
            self.resumes,
            self.logs,
            self.artifacts,
        ):
            path.mkdir(parents=True, exist_ok=True)


def get_app_paths() -> AppPaths:
    config_override = os.environ.get("NAUKRI_AUTO_CONFIG_DIR")
    data_override = os.environ.get("NAUKRI_AUTO_DATA_DIR")

    if config_override:
        config_dir = Path(config_override).expanduser()
    elif sys.platform == "win32":
        config_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / APP_NAME
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library/Application Support" / APP_NAME
    else:
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME

    if data_override:
        data_dir = Path(data_override).expanduser()
    elif sys.platform == "win32":
        data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / APP_NAME
    elif sys.platform == "darwin":
        data_dir = Path.home() / "Library/Application Support" / APP_NAME
    else:
        data_dir = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / APP_NAME

    return AppPaths(config_dir=config_dir, data_dir=data_dir)
