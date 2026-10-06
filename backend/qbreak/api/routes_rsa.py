"""Public-key breach-test API routes."""

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from qbreak.api.schemas import (
    RSAAttackRequest,
    RSAAttackResponse,
    RSAEncryptRequest,
    RSAEncryptResponse,
    RSAKeygenRequest,
    RSAKeygenResponse,
)
from qbreak.common.simulator import SimulatorBusyError
from qbreak.services import rsa_service

router = APIRouter(prefix="/rsa", tags=["public-key breach test"])


async def _run(service: Callable[[object], dict], req: object) -> dict:
    try:
        return await asyncio.wait_for(run_in_threadpool(service, req), timeout=60)
    except SimulatorBusyError as exc:
        raise HTTPException(status_code=503, detail="Simulator busy, try again") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Simulation exceeded the 60 second request limit") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/keygen", response_model=RSAKeygenResponse)
async def keygen(req: RSAKeygenRequest) -> dict:
    """Generate a miniature RSA key pair for the organization."""
    return await _run(rsa_service.keygen, req)


@router.post("/encrypt", response_model=RSAEncryptResponse)
async def encrypt(req: RSAEncryptRequest) -> dict:
    """Encrypt a message with the miniature public key."""
    return await _run(rsa_service.encrypt, req)


@router.post("/attack", response_model=RSAAttackResponse)
async def attack(req: RSAAttackRequest) -> dict:
    """Run the simulated quantum adversary against public data."""
    return await _run(rsa_service.attack, req)


@router.get("/resource-estimate")
def resource_estimate(modulus_bits: int = Query(default=2048, ge=8, le=16384)) -> dict:
    """Cited, published resource estimates for factoring real-scale RSA (no simulation)."""
    from qbreak.rsa.resource_estimate import estimate_rsa_resources

    return estimate_rsa_resources(modulus_bits)
