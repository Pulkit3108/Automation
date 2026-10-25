from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class Outcome(StrEnum):
    SUCCESS = "SUCCESS"
    DRY_RUN_SUCCESS = "DRY_RUN_SUCCESS"
    CONFIG_ERROR = "CONFIG_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SITE_CHANGED = "SITE_CHANGED"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    ALREADY_RUNNING = "ALREADY_RUNNING"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


EXIT_CODES = {
    Outcome.SUCCESS: 0,
    Outcome.DRY_RUN_SUCCESS: 0,
    Outcome.CONFIG_ERROR: 2,
    Outcome.AUTH_REQUIRED: 3,
    Outcome.SITE_CHANGED: 4,
    Outcome.UPLOAD_FAILED: 5,
    Outcome.NETWORK_ERROR: 6,
    Outcome.ALREADY_RUNNING: 7,
    Outcome.DEPENDENCY_ERROR: 8,
    Outcome.INTERNAL_ERROR: 10,
}


@dataclass(frozen=True)
class RunResult:
    outcome: Outcome
    message: str
    timestamp_utc: str
    artifact_dir: str | None = None

    @classmethod
    def create(
        cls, outcome: Outcome, message: str, artifact_dir: Path | None = None
    ) -> RunResult:
        return cls(
            outcome=outcome,
            message=message,
            timestamp_utc=datetime.now(UTC).isoformat(),
            artifact_dir=str(artifact_dir) if artifact_dir else None,
        )

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.outcome]

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        payload["outcome"] = self.outcome.value
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
