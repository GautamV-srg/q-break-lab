"""Quantum-risk framing routes (Mosca's X + Y > Z inequality)."""

from fastapi import APIRouter, HTTPException

from qbreak.api.schemas import MoscaInfoResponse, MoscaRequest, MoscaResponse
from qbreak.risk.mosca import mosca_info, mosca_risk

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/mosca", response_model=MoscaInfoResponse)
def mosca_defaults() -> dict:
    """Default inputs, explanation and citation for the Mosca calculator."""
    return mosca_info()


@router.post("/mosca", response_model=MoscaResponse)
def mosca(req: MoscaRequest) -> dict:
    """Evaluate X + Y > Z for the given years."""
    try:
        return mosca_risk(req.x, req.y, req.z)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
