from fastapi import APIRouter
from app.schemas.drift import DriftClassifyRequest, DriftClassifyResponse
from app.services.drift_classifier_service import MultiCategoryDriftClassifier

router = APIRouter(prefix="/api/v1/drift", tags=["FE04 - 5.1 Drift Classifier"])


@router.post("/classify", response_model=DriftClassifyResponse)
def classify_documentation_drift(payload: DriftClassifyRequest) -> DriftClassifyResponse:
    classifier = MultiCategoryDriftClassifier()
    return classifier.classify(payload)