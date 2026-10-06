"""FastAPI application entry point and production static-file host."""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from qbreak.api.routes_aes import router as aes_router
from qbreak.api.routes_evaluation import router as evaluation_router
from qbreak.api.routes_rsa import router as rsa_router
from qbreak.api.schemas import ConfigResponse
from qbreak.config import (
    AES_NOISE_MAX_KEY_BITS,
    ENABLED_KEY_BITS,
    ENABLED_MODULI,
    KEY_BITS_16_NOTE,
    MAX_AES_TEXT_CHARS,
    MAX_NOISE_P,
    MAX_NOISY_SHOTS,
    MAX_RSA_TEXT_CHARS,
    MAX_SHOTS,
    SYMMETRIC_MAX_KEY_BITS,
    aes_key_options,
)

AES_CONDITION_INFO = [
    {"id": "known_beginning", "label": "Known beginning", "needs_known_text": True,
     "description": "The attacker knows how the message starts (e.g. a standard greeting)."},
    {"id": "known_substring", "label": "Known substring", "needs_known_text": True,
     "description": "The attacker knows a piece of text that appears somewhere in the message, position unknown."},
    {"id": "ciphertext_only", "label": "Ciphertext only", "needs_known_text": False,
     "description": "No known plaintext: a key is a candidate if the whole message decrypts to ASCII text. "
     "Expect several candidates (an Ambiguous verdict)."},
]

app = FastAPI(title="Q-Break API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(aes_router, prefix="/api")
app.include_router(rsa_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def readable_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return the first validation failure as a readable contract error."""
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"] if part != "body")
    message = str(error["msg"]).removeprefix("Value error, ")
    detail = f"{location}: {message}" if location else message
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report whether the API process is ready to accept requests."""
    return {"status": "ok"}


@app.get("/api/config", response_model=ConfigResponse)
def config() -> dict:
    """Return enabled test sizes and public request limits."""
    from qbreak.aes.counting import COUNTING_MAX_KEY_BITS

    return {
        "aes_key_bits": ENABLED_KEY_BITS,
        "rsa_moduli": ENABLED_MODULI,
        "max_shots": MAX_SHOTS,
        "max_aes_text_chars": MAX_AES_TEXT_CHARS,
        "max_rsa_text_chars": MAX_RSA_TEXT_CHARS,
        "default_known_prefix_chars": 3,
        "aes_key_options": aes_key_options(),
        "aes_max_key_bits": SYMMETRIC_MAX_KEY_BITS,
        "aes_key_bits_16_note": KEY_BITS_16_NOTE,
        "aes_conditions": AES_CONDITION_INFO,
        "aes_counting_max_key_bits": COUNTING_MAX_KEY_BITS,
        "aes_noise_max_key_bits": AES_NOISE_MAX_KEY_BITS,
        "aes_max_noise_p": MAX_NOISE_P,
        "aes_max_noisy_shots": MAX_NOISY_SHOTS,
    }


static_dir = Path(os.getenv("STATIC_DIR", "/app/static"))
if static_dir.is_dir():
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str) -> FileResponse:
        """Serve a static file or the SPA entry point for client-side routes."""
        requested = (static_dir / path).resolve()
        try:
            requested.relative_to(static_dir.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(static_dir / "index.html")
