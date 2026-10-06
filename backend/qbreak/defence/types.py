"""Shared types and helpers for the three defences.

Every defence returns a ``ProtectResult``: a **public bundle** (what an eavesdropper on the
network would see) plus server-side measurements. Keys, shared secrets and the plaintext
never enter a bundle; ``SECRET_FIELD_NAMES`` lists the names the blind re-attack refuses.
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

Method = Literal["aes256", "mlkem", "bb84"]

SECRET_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "plaintext",
        "key",
        "key_b64",
        "aes_key",
        "aes_key_b64",
        "decapsulation_key",
        "decapsulation_key_b64",
        "shared_secret",
        "shared_secret_b64",
        "bb84_key",
        "final_key",
        "alice_bits",
        "bob_bits",
        "sifted_key",
    }
)
"""Field names that would hand the attacker a secret. Never in a bundle; rejected by re-attack."""

NONCE_BYTES = 12
"""96-bit GCM nonce, as recommended by NIST SP 800-38D."""
GCM_TAG_BYTES = 16

CITATIONS: dict[str, str] = {
    "FIPS197": "NIST FIPS 197, \"Advanced Encryption Standard (AES)\", 2001 (updated 2023).",
    "SP800-38D": "NIST SP 800-38D, \"Recommendation for Block Cipher Modes of Operation: "
    "Galois/Counter Mode (GCM) and GMAC\", 2007.",
    "FIPS203": "NIST FIPS 203, \"Module-Lattice-Based Key-Encapsulation Mechanism Standard\" "
    "(ML-KEM), August 2024.",
    "RFC5869": "H. Krawczyk, P. Eronen, \"HMAC-based Extract-and-Expand Key Derivation Function "
    "(HKDF)\", RFC 5869, 2010.",
    "BB84": "C. H. Bennett, G. Brassard, \"Quantum cryptography: Public key distribution and coin "
    "tossing\", Proc. IEEE Int. Conf. on Computers, Systems and Signal Processing, Bangalore, "
    "1984, pp. 175-179 (reprinted in Theor. Comput. Sci. 560, 2014, pp. 7-11).",
    "SP2000": "P. W. Shor, J. Preskill, \"Simple proof of security of the BB84 quantum key "
    "distribution protocol\", Phys. Rev. Lett. 85, 441 (2000) — the ~11% QBER threshold.",
    "GLRS16": "M. Grassl, B. Langenberg, M. Roetteler, R. Steinwandt, \"Applying Grover's "
    "algorithm to AES: quantum resource estimates\", PQCrypto 2016, LNCS 9606, pp. 29-43, "
    "arXiv:1512.04965.",
    "NIST16": "NIST, \"Submission Requirements and Evaluation Criteria for the Post-Quantum "
    "Cryptography Standardization Process\", Call for Proposals, 2016, Section 4.A.5.",
    "SHOR97": "P. W. Shor, \"Polynomial-Time Algorithms for Prime Factorization and Discrete "
    "Logarithms on a Quantum Computer\", SIAM J. Comput. 26(5), 1997, pp. 1484-1509.",
    "KYBERPY": "G. Pope et al., kyber-py: a pure-Python implementation of ML-KEM (FIPS 203), "
    "https://github.com/GiacomoPope/kyber-py — educational, not constant-time.",
}

MLKEM_HONESTY_NOTE = (
    "ML-KEM here comes from kyber-py, an educational pure-Python implementation of FIPS 203. "
    "It is not constant-time and not side-channel hardened; production systems should use a "
    "vetted library (for example liboqs, BoringSSL or the OS crypto provider)."
)
BB84_HONESTY_NOTE = (
    "BB84 is simulated in Qiskit Aer: photons are qubits, the channel is a noise model, and the "
    "eavesdropper is an intercept-resend attack. Reconciliation is a simplified block-parity / "
    "binary-search scheme (no Cascade back-tracking) and privacy amplification is a single "
    "SHA-256 hash; real QKD links use authenticated classical channels, finite-key analysis and "
    "universal hashing."
)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


class Stopwatch:
    """Collects named timings in milliseconds."""

    def __init__(self) -> None:
        self.timings_ms: dict[str, float] = {}

    def time(self, name: str):
        watch = self

        class _Lap:
            def __enter__(self) -> None:
                self.t0 = time.perf_counter()

            def __exit__(self, *exc: object) -> None:
                watch.timings_ms[name] = round((time.perf_counter() - self.t0) * 1000, 3)

        return _Lap()


def gcm_seal(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """AES-256-GCM encrypt with a fresh random 96-bit nonce: (nonce, ciphertext || tag)."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, None)


def gcm_open(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """AES-256-GCM decrypt; raises cryptography.exceptions.InvalidTag on any tampering."""
    return AESGCM(key).decrypt(nonce, ciphertext, None)


@dataclass
class ProtectResult:
    """One defence applied to the message: public bundle plus server-side measurements."""

    method: Method
    status: Literal["protected", "aborted"]
    bundle: dict[str, Any] | None
    sizes: dict[str, int]
    timings_ms: dict[str, float]
    roundtrip_ok: bool
    steps: list[str]
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "status": self.status,
            "bundle": self.bundle,
            "sizes": self.sizes,
            "timings_ms": self.timings_ms,
            "roundtrip_ok": self.roundtrip_ok,
            "steps": self.steps,
            **self.extra,
        }


def public_metrics(sizes: dict[str, int], timings_ms: dict[str, float]) -> dict[str, Any]:
    """Non-secret measurements carried inside a bundle so the comparison can cite them."""
    return {"sizes": dict(sizes), "timings_ms": dict(timings_ms)}
