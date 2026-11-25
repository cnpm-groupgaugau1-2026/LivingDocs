from fastapi import APIRouter

from app.services.ci_policy_service import (
    MergePolicyConfig,
    PREvaluationRequest,
    PREvaluationRun,
    ci_policy_service,
)

router = APIRouter(prefix="/api/v1/ci-policy", tags=["fe06-ci-policy"])


@router.get("/policy", response_model=MergePolicyConfig)
def get_policy() -> MergePolicyConfig:
    return ci_policy_service.get_policy()


@router.put("/policy", response_model=MergePolicyConfig)
def update_policy(payload: MergePolicyConfig) -> MergePolicyConfig:
    return ci_policy_service.update_policy(payload)


@router.get("/runs", response_model=list[PREvaluationRun])
def get_runs() -> list[PREvaluationRun]:
    return ci_policy_service.list_runs()


@router.post("/evaluate-pr", response_model=PREvaluationRun)
def evaluate_pr(req: PREvaluationRequest) -> PREvaluationRun:
    return ci_policy_service.evaluate_pr(req)