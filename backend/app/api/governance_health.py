from fastapi import APIRouter, HTTPException, Query

from app.services.governance_health_service import (
    ComplianceExportPayload,
    ExportFormat,
    GovernanceOverview,
    ImpactAnalysisResult,
    governance_health_service,
)

router = APIRouter(
    prefix="/api/v1/governance-health", tags=["fe10-governance-health"]
)


@router.get("/overview", response_model=GovernanceOverview)
def get_overview() -> GovernanceOverview:
    return governance_health_service.get_overview()


@router.get("/impact", response_model=ImpactAnalysisResult)
def get_impact(node_id: str = Query(..., min_length=1)) -> ImpactAnalysisResult:
    try:
        return governance_health_service.analyze_impact(node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/export", response_model=ComplianceExportPayload)
def export_report(format: ExportFormat = Query("markdown")) -> ComplianceExportPayload:
    return governance_health_service.export_compliance_report(format)