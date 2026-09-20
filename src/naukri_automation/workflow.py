from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from naukri_automation.browser_session import BrowserDependencyError, BrowserSession
from naukri_automation.config import AppConfig, ConfigurationError
from naukri_automation.naukri_site import (
    AuthenticationRequired,
    NaukriSite,
    SiteContractError,
    UploadVerificationError,
)
from naukri_automation.notifications import send_notification
from naukri_automation.paths import AppPaths
from naukri_automation.result import Outcome, RunResult
from naukri_automation.run_lock import AlreadyRunningError, RunLock

LOGGER = logging.getLogger(__name__)
BrowserFactory = Callable[..., Any]
SiteFactory = Callable[..., Any]


def execute(
    config: AppConfig,
    paths: AppPaths,
    *,
    dry_run: bool = False,
    headed: bool = False,
    browser_factory: BrowserFactory = BrowserSession,
    site_factory: SiteFactory = NaukriSite,
) -> RunResult:
    try:
        config.validate(require_resume=True)
    except ConfigurationError as error:
        return _finish(
            RunResult.create(Outcome.CONFIG_ERROR, str(error)), config, paths
        )

    paths.ensure_runtime_dirs()
    _remove_expired_artifacts(paths.artifacts, config.artifact_retention_days)

    try:
        with RunLock(paths.run_lock):
            return _execute_locked(
                config,
                paths,
                dry_run=dry_run,
                headed=headed,
                browser_factory=browser_factory,
                site_factory=site_factory,
            )
    except AlreadyRunningError:
        return _finish(
            RunResult.create(Outcome.ALREADY_RUNNING, "another automation run is active"),
            config,
            paths,
        )


def _execute_locked(
    config: AppConfig,
    paths: AppPaths,
    *,
    dry_run: bool,
    headed: bool,
    browser_factory: BrowserFactory,
    site_factory: SiteFactory,
) -> RunResult:
    session: Any = None
    artifact_dir: Path | None = None
    try:
        with browser_factory(
            paths.browser_profile,
            headless=False if headed else config.headless,
            timeout_seconds=config.timeout_seconds,
        ) as session:
            try:
                site = site_factory(session.page, timeout_seconds=config.timeout_seconds)
                site.open_profile()
                site.inspect_resume_section()
                if dry_run:
                    return _finish(
                        RunResult.create(
                            Outcome.DRY_RUN_SUCCESS,
                            "dry run succeeded; resume upload control is available",
                        ),
                        config,
                        paths,
                    )

                site.upload_resume(config.resume_path.expanduser())
                return _finish(
                    RunResult.create(
                        Outcome.SUCCESS,
                        "resume upload was verified by the Naukri profile UI",
                    ),
                    config,
                    paths,
                )
            except Exception:
                artifact_dir = _new_artifact_dir(paths.artifacts)
                session.capture_failure(artifact_dir)
                raise
    except BrowserDependencyError as error:
        result = RunResult.create(Outcome.DEPENDENCY_ERROR, str(error))
    except AuthenticationRequired:
        result = RunResult.create(
            Outcome.AUTH_REQUIRED,
            "login is required; run 'naukri-auto login --headed'",
            artifact_dir,
        )
    except SiteContractError:
        result = RunResult.create(
            Outcome.SITE_CHANGED,
            "the Naukri profile page no longer matches the expected contract",
            artifact_dir,
        )
    except UploadVerificationError:
        result = RunResult.create(
            Outcome.UPLOAD_FAILED,
            "the upload result could not be verified; do not retry automatically",
            artifact_dir,
        )
    except Exception as error:
        LOGGER.exception("automation run failed with %s", type(error).__name__)
        outcome = (
            Outcome.NETWORK_ERROR
            if "timeout" in type(error).__name__.lower()
            else Outcome.INTERNAL_ERROR
        )
        result = RunResult.create(
            outcome,
            "the browser workflow failed; inspect the local diagnostic artifacts",
            artifact_dir,
        )

    return _finish(result, config, paths)


def _finish(result: RunResult, config: AppConfig, paths: AppPaths) -> RunResult:
    result.write(paths.last_result)
    send_notification(config.notification, result)
    return result


def _new_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate = root / timestamp
    suffix = 1
    while candidate.exists():
        candidate = root / f"{timestamp}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def _remove_expired_artifacts(root: Path, retention_days: int) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    for child in root.iterdir() if root.exists() else ():
        if not child.is_dir():
            continue
        modified = datetime.fromtimestamp(child.stat().st_mtime, UTC)
        if modified < cutoff:
            shutil.rmtree(child)
