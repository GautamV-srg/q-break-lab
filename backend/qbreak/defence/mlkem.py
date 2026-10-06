"""Defence 2: ML-KEM-768 (FIPS 203) key encapsulation + AES-256-GCM (the KEM + DEM pattern).

ML-KEM does not encrypt messages. The receiver publishes an encapsulation key; the sender
encapsulates a fresh 32-byte shared secret against it; both derive an AES-256 key from the
secret with HKDF-SHA256, and the message travels under AES-256-GCM.

Library: kyber-py (``kyber_py.ml_kem.ML_KEM_768``), pinned in pyproject.toml. Its API,
verified against the installed 1.2.0: ``keygen() -> (ek, dk)``, ``encaps(ek) -> (K, c)``,
``decaps(dk, c) -> K``. It is an educational implementation (see ``MLKEM_HONESTY_NOTE``).
"""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from kyber_py.ml_kem import ML_KEM_768

from qbreak.defence.types import (
    GCM_TAG_BYTES,
    MLKEM_HONESTY_NOTE,
    NONCE_BYTES,
    ProtectResult,
    Stopwatch,
    b64,
    gcm_open,
    gcm_seal,
    public_metrics,
)

PARAMETER_SET = "ML-KEM-768"
HKDF_INFO = b"q-break ml-kem-768 -> aes-256-gcm"


def derive_aes_key(shared_secret: bytes) -> bytes:
    """HKDF-SHA256 (RFC 5869) from the 32-byte KEM shared secret to a 32-byte AES key."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=HKDF_INFO).derive(shared_secret)


def protect_mlkem(plaintext: str) -> ProtectResult:
    """Receiver keygen, sender encaps + encrypt, receiver decaps + decrypt; verify the round trip."""
    data = plaintext.encode("utf-8")
    watch = Stopwatch()
    with watch.time("keygen"):
        encapsulation_key, decapsulation_key = ML_KEM_768.keygen()
    with watch.time("encaps"):
        shared_secret, kem_ciphertext = ML_KEM_768.encaps(encapsulation_key)
    with watch.time("encrypt"):
        nonce, ciphertext = gcm_seal(derive_aes_key(shared_secret), data)
    with watch.time("decaps"):
        receiver_secret = ML_KEM_768.decaps(decapsulation_key, kem_ciphertext)
    with watch.time("decrypt"):
        roundtrip_ok = receiver_secret == shared_secret and gcm_open(derive_aes_key(receiver_secret), nonce, ciphertext) == data
    sizes = {
        "plaintext_bytes": len(data),
        "encapsulation_key_bytes": len(encapsulation_key),
        "decapsulation_key_bytes": len(decapsulation_key),
        "kem_ciphertext_bytes": len(kem_ciphertext),
        "shared_secret_bytes": len(shared_secret),
        "ciphertext_bytes": len(ciphertext),
        "tag_bytes": GCM_TAG_BYTES,
        "nonce_bytes": NONCE_BYTES,
    }
    steps = [
        f"Receiver generated an {PARAMETER_SET} key pair: a {len(encapsulation_key)}-byte public "
        f"encapsulation key and a {len(decapsulation_key)}-byte decapsulation key (kept secret).",
        f"Sender encapsulated against the public key: a {len(shared_secret)}-byte shared secret and "
        f"a {len(kem_ciphertext)}-byte KEM ciphertext.",
        "Sender derived an AES-256 key from the shared secret with HKDF-SHA256 and encrypted the "
        f"message with AES-256-GCM → {len(ciphertext)} bytes.",
        "Receiver decapsulated the KEM ciphertext, re-derived the same key and decrypted: "
        + ("the message matches." if roundtrip_ok else "MISMATCH."),
        "Public bundle: encapsulation key, KEM ciphertext, message ciphertext and nonce. "
        "No key or shared secret is returned.",
        "Educational implementation: " + MLKEM_HONESTY_NOTE,
    ]
    bundle = {
        "parameter_set": PARAMETER_SET,
        "encapsulation_key_b64": b64(encapsulation_key),
        "kem_ciphertext_b64": b64(kem_ciphertext),
        "ciphertext_b64": b64(ciphertext),
        "nonce_b64": b64(nonce),
        "public_metrics": public_metrics(sizes, watch.timings_ms),
    }
    del decapsulation_key, shared_secret, receiver_secret
    return ProtectResult(
        "mlkem",
        "protected",
        bundle,
        sizes,
        watch.timings_ms,
        roundtrip_ok,
        steps,
        extra={"parameter_set": PARAMETER_SET, "honesty_note": MLKEM_HONESTY_NOTE},
    )
