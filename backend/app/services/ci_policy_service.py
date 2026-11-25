from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_FILE = DATA_DIR / "fe06_ci_policy_state.json"

SeverityLevel = Literal["low", "medium", "high", "critical"]
PolicyMode = Literal["warn", "block"]
DecisionType = Literal["allow", "warn", "block"]


class MergePolicyConfig(BaseModel):
    mode: PolicyMode = "block"
    block_on_severities: list[SeverityLevel] = Field(
        default_factory=lambda: ["critical"]
    )
    protected_paths: list[str] = Field(
        default_factory=lambda: ["backend/app/api/", "backend/app/services/"]
    )
    doc_paths: list[str] = Field(
        default_factory=lambda: ["docs/"]
    )
    allow_override_label: str = "docs-drift-waived"
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PREvaluationRequest(BaseModel):
    repo: str = "livingdocs/repo"
    pr_number: int = 101
    base_sha: str = "HEAD~1"
    head_sha: str = "HEAD"
    changed_files: list[str] = Field(
        default_factory=lambda: ["backend/app/api/review_workflow.py"]
    )
    labels: list[str] = Field(default_factory=list)
    detected_severity: SeverityLevel = "critical"
    drift_summary: str = "API endpoint changed without updating corresponding documentation."


class PREvaluationRun(BaseModel):
    run_id: str
    repo: str
    pr_number: int
    base_sha: str
    head_sha: str
    policy_mode: PolicyMode
    detected_severity: SeverityLevel
    drift_detected: bool
    waived_by_label: bool
    decision: DecisionType
    exit_code: int
    reason: str
    affected_code_files: list[str]
    missing_doc_updates: bool
    evaluated_at: str


class CIPolicyState(BaseModel):
    policy: MergePolicyConfig
    runs: list[PREvaluationRun]


class CIPolicyService:
    def __init__(self, storage_path: Path = DATA_FILE) -> None:
        self.storage_path = storage_path
        self._state = self._load_or_init()

    def _load_or_init(self) -> CIPolicyState:
        if self.storage_path.exists():
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return CIPolicyState.model_validate(raw)

        initial = CIPolicyState(
            policy=MergePolicyConfig(),
            runs=[
                PREvaluationRun(
                    run_id="run-fe06-001",
                    repo="livingdocs/repo",
                    pr_number=48,
                    base_sha="abc1234",
                    head_sha="def5678",
                    policy_mode="block",
                    detected_severity="critical",
                    drift_detected=True,
                    waived_by_label=False,
                    decision="block",
                    exit_code=1,
                    reason="Critical documentation drift detected on protected code paths without matching docs/ changes.",
                    affected_code_files=["backend/app/api/review_workflow.py"],
                    missing_doc_updates=True,
                    evaluated_at=datetime.now(timezone.utc).isoformat(),
                )
            ],
        )
        self._save(initial)
        return initial

    def _save(self, state: CIPolicyState) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

    def get_policy(self) -> MergePolicyConfig:
        return self._state.policy

    def update_policy(self, payload: MergePolicyConfig) -> MergePolicyConfig:
        payload.updated_at = datetime.now(timezone.utc).isoformat()
        self._state.policy = payload
        self._save(self._state)
        return self._state.policy

    def list_runs(self) -> list[PREvaluationRun]:
        return self._state.runs

    def evaluate_pr(self, req: PREvaluationRequest) -> PREvaluationRun:
        policy = self._state.policy

        affected_code = [
            f
            for f in req.changed_files
            if any(f.startswith(prefix) for prefix in policy.protected_paths)
        ]
        has_doc_changes = any(
            f.startswith(prefix) for f in req.changed_files for prefix in policy.doc_paths
        )
        missing_doc_updates = len(affected_code) > 0 and not has_doc_changes
        drift_detected = missing_doc_updates or req.detected_severity in ("high", "critical")
        waived = policy.allow_override_label in req.labels

        severity_triggered = req.detected_severity in policy.block_on_severities

        if not drift_detected or not severity_triggered:
            decision: DecisionType = "allow"
            exit_code = 0
            reason = "No policy-violating documentation drift detected."
        elif waived:
            decision = "warn"
            exit_code = 0
            reason = f"Drift waived via PR label '{policy.allow_override_label}'; merge allowed with warning."
        elif policy.mode == "warn":
            decision = "warn"
            exit_code = 0
            reason = f"[WARN] {req.detected_severity.upper()} drift detected; policy mode is 'warn' so PR merge is not blocked."
        else:
            decision = "block"
            exit_code = 1
            reason = f"[BLOCKED] {req.detected_severity.upper()} drift detected; policy mode is 'block'."

        run = PREvaluationRun(
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            repo=req.repo,
            pr_number=req.pr_number,
            base_sha=req.base_sha,
            head_sha=req.head_sha,
            policy_mode=policy.mode,
            detected_severity=req.detected_severity,
            drift_detected=drift_detected,
            waived_by_label=waived,
            decision=decision,
            exit_code=exit_code,
            reason=reason,
            affected_code_files=affected_code,
            missing_doc_updates=missing_doc_updates,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._state.runs.insert(0, run)
        self._save(self._state)
        return run


ci_policy_service = CIPolicyService()