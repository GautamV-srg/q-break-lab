"""Defence 1: AES-256-GCM, real encryption of the organization's message.

Grover's search only square-roots a key search, so a 256-bit key keeps about 128 bits of
security against a quantum attacker. The key never leaves this function.
"""

from __future__ import annotations

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from qbreak.defence.types import (
    GCM_TAG_BYTES,
    NONCE_BYTES,
    ProtectResult,
    Stopwatch,
    b64,
    gcm_open,
    gcm_seal,
    public_metrics,
)

KEY_BITS = 256


def protect_aes256(plaintext: str) -> ProtectResult:
    """Encrypt with a fresh random AES-256 key and 96-bit nonce, then verify the round trip."""
    data = plaintext.encode("utf-8")
    watch = Stopwatch()
    with watch.time("keygen"):
        key = AESGCM.generate_key(bit_length=KEY_BITS)
    with watch.time("encrypt"):
        nonce, ciphertext = gcm_seal(key, data)
    with watch.time("decrypt"):
        roundtrip_ok = gcm_open(key, nonce, ciphertext) == data
    sizes = {
        "plaintext_bytes": len(data),
        "ciphertext_bytes": len(ciphertext),
        "tag_bytes": GCM_TAG_BYTES,
        "nonce_bytes": NONCE_BYTES,
        "key_bytes": len(key),
    }
    steps = [
        f"Generated a fresh random {KEY_BITS}-bit AES key (kept on the server, never returned).",
        f"Generated a random {NONCE_BYTES * 8}-bit nonce.",
        f"Encrypted the {len(data)}-byte UTF-8 message with AES-256-GCM → {len(ciphertext)} bytes "
        f"(ciphertext plus a {GCM_TAG_BYTES}-byte authentication tag).",
        "Decrypted server-side with the same key and nonce: "
        + ("the message matches." if roundtrip_ok else "MISMATCH."),
        "Public bundle: ciphertext and nonce only.",
    ]
    bundle = {
        "ciphertext_b64": b64(ciphertext),
        "nonce_b64": b64(nonce),
        "public_metrics": public_metrics(sizes, watch.timings_ms),
    }
    del key
    return ProtectResult("aes256", "protected", bundle, sizes, watch.timings_ms, roundtrip_ok, steps)
