"""Symmetric breach-test API routes."""

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from qbreak.api.schemas import (
    AESAttackRequest,
    AESAttackResponse,
    AESEncryptRequest,
    AESEncryptResponse,
)
from qbreak.common.simulator import SimulatorBusyError
from qbreak.config import AES_REQUEST_TIMEOUT_S
from qbreak.services import aes_service

router = APIRouter(prefix="/aes", tags=["symmetric breach test"])


async def _run(service: Callable[[object], dict], req: object) -> dict:
    try:
        return await asyncio.wait_for(run_in_threadpool(service, req), timeout=AES_REQUEST_TIMEOUT_S)
    except SimulatorBusyError as exc:
        raise HTTPException(status_code=503, detail="Simulator busy, try again") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"Simulation exceeded the {AES_REQUEST_TIMEOUT_S:g} second request limit") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/encrypt", response_model=AESEncryptResponse)
async def encrypt(req: AESEncryptRequest) -> dict:
    """Encrypt a miniature symmetric test message."""
    return await _run(aes_service.encrypt, req)


@router.post("/attack", response_model=AESAttackResponse)
async def attack(req: AESAttackRequest) -> dict:
    """Run the simulated quantum adversary against intercepted data."""
    return await _run(aes_service.attack, req)


@router.get("/resources")
def resources() -> dict:
    """Published resource estimates for a Grover key search on real AES-128/192/256 (cited)."""
    from qbreak.aes.resources import all_aes_estimates

    return all_aes_estimates()
