"""Defence API routes: protect, blind re-attack, and the static comparison info."""

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from qbreak.api.schemas import (
    DefenceInfoResponse,
    ProtectRequest,
    ProtectResponse,
    ReattackRequest,
    ReattackResponse,
)
from qbreak.common.simulator import SimulatorBusyError
from qbreak.config import DEFENCE_REQUEST_TIMEOUT_S
from qbreak.services import defence_service

router = APIRouter(prefix="/defence", tags=["defence"])


async def _run(service: Callable[[object], dict], req: object) -> dict:
    try:
        return await asyncio.wait_for(run_in_threadpool(service, req), timeout=DEFENCE_REQUEST_TIMEOUT_S)
    except SimulatorBusyError as exc:
        raise HTTPException(status_code=503, detail="Simulator busy, try again") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"Simulation exceeded the {DEFENCE_REQUEST_TIMEOUT_S:g} second request limit") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/protect", response_model=ProtectResponse)
async def protect(req: ProtectRequest) -> dict:
    """Organization side: protect the message with AES-256, ML-KEM-768 and/or BB84 QKD."""
    return await _run(defence_service.protect, req)


@router.post("/reattack", response_model=ReattackResponse)
async def reattack(req: ReattackRequest) -> dict:
    """Attacker side (blind): public bundles only; secret or plaintext fields are rejected (422)."""
    return await _run(defence_service.reattack, req)


@router.get("/info", response_model=DefenceInfoResponse)
def info() -> dict:
    """Static comparison rows, citations, BB84 defaults and limits, and honesty notes."""
    from qbreak.defence.compare import defence_info

    return defence_info()
