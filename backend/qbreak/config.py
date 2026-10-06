"""Environment-driven limits and enabled miniature attack sizes."""

import os


def _integer_list(name: str, default: str) -> list[int]:
    raw = os.getenv(name, default)
    try:
        values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError(f"{name} must be a comma-separated list of integers.") from exc
    if not values:
        raise ValueError(f"{name} must enable at least one value.")
    return values


MAX_SHOTS = 4096

# --------------------------------------------------------------------------------------
# Symmetric breach test (MiniAES + Grover) — owned by Backend A. RSA settings live in the
# RSA section below; keep edits inside your own section.
# --------------------------------------------------------------------------------------

SIMULATED_KEY_BITS: tuple[int, ...] = (4, 6, 8, 10, 12)
"""Every key size the simulator can run. 16-bit is listed in config but never simulated."""

REQUESTED_KEY_BITS: list[int] = _integer_list("QBREAK_KEY_BITS", "4,6,8,10,12")
"""Key sizes this instance was asked to enable (QBREAK_KEY_BITS). Locally every simulated size
is on; Docker and Render set QBREAK_KEY_BITS=4 for their small instances."""

SYMMETRIC_MAX_KEY_BITS: int = int(os.getenv("SYMMETRIC_MAX_KEY_BITS", os.getenv("QBREAK_SYMMETRIC_MAX_KEY_BITS", "12")))
"""Memory cap: 12-bit needs an instance with about 2 GB RAM, so constrained deploys set 8 or 10."""

ENABLED_KEY_BITS: list[int] = [b for b in REQUESTED_KEY_BITS if b in SIMULATED_KEY_BITS and b <= SYMMETRIC_MAX_KEY_BITS]
"""The effective key sizes: requested, simulatable, and within the memory cap."""

MAX_AES_TEXT_CHARS = 1000

AES_CONDITIONS: tuple[str, ...] = ("known_beginning", "known_substring", "ciphertext_only")

AES_REQUEST_TIMEOUT_S: float = float(os.getenv("QBREAK_AES_TIMEOUT_S", "900"))
"""Per-request limit for symmetric simulations. 12-bit attacks take about 6-9 minutes on a fast
multi-core PC (10-bit ciphertext-only about 1.5 minutes), hence 15 minutes by default."""

AES_NOISE_MAX_KEY_BITS: int = int(os.getenv("QBREAK_NOISE_MAX_KEY_BITS", "4"))
"""Noisy runs simulate every shot separately, so the noise option is limited to small keys."""

MAX_NOISE_P = 0.05
MAX_NOISY_SHOTS = 64

KEY_BITS_16_NOTE = (
    "16-bit keys are not simulated. Every extra qubit doubles the simulator's memory: a "
    "16-bit attack needs about 30 qubits, i.e. a state vector of 2^30 complex amplitudes "
    "(about 16 GB), and about 200 Grover iterations (π/4·√65536 ≈ 201), each a full pass "
    "over that state. That is out of scope for this classical simulator — which is itself "
    "the point: brute-forcing quantum circuits classically does not scale, and real attacks "
    "would need real, fault-tolerant quantum hardware."
)


def aes_key_options() -> list[dict]:
    """Every key size the UI may show, with whether it is enabled here and why not."""
    options = []
    for bits in (*SIMULATED_KEY_BITS, 16):
        reason = None
        if bits == 16:
            reason = KEY_BITS_16_NOTE
        elif bits > SYMMETRIC_MAX_KEY_BITS:
            reason = (
                f"Not enabled on this instance: {bits}-bit keys need more memory than this "
                f"deploy allows (SYMMETRIC_MAX_KEY_BITS={SYMMETRIC_MAX_KEY_BITS}; 12-bit needs about 2 GB RAM)."
            )
        elif bits not in REQUESTED_KEY_BITS:
            reason = f"Not enabled on this instance (QBREAK_KEY_BITS does not include {bits})."
        options.append({"bits": bits, "enabled": reason is None, "simulated": bits != 16, "reason": reason})
    return options


def key_bits_rejection(bits: int) -> str:
    """The config-driven reason a key size is rejected."""
    for option in aes_key_options():
        if option["bits"] == bits and option["reason"]:
            return f"key_bits {bits}: {option['reason']}"
    return f"key_bits must be one of {ENABLED_KEY_BITS}"


# --------------------------------------------------------------------------------------
# Public-key breach test (MiniRSA + Shor) — owned by Backend B.
# --------------------------------------------------------------------------------------

# Every modulus the attack implements: products of two distinct odd primes <= 11.
RSA_MODULI_CATALOGUE: tuple[int, ...] = (15, 21, 33, 35, 55, 77)
# Moduli enabled on this instance (QBREAK_MODULI narrows it on constrained deploys).
ENABLED_MODULI: list[int] = _integer_list("QBREAK_MODULI", ",".join(map(str, RSA_MODULI_CATALOGUE)))
if not set(ENABLED_MODULI) <= set(RSA_MODULI_CATALOGUE):
    raise ValueError(f"QBREAK_MODULI may only enable moduli from {list(RSA_MODULI_CATALOGUE)}.")
MAX_RSA_TEXT_CHARS = 300
# Moduli shown as disabled choices, each with the one-line reason the UI displays.
RSA_DISABLED_MODULI: tuple[dict, ...] = (
    {
        "n": 22,
        "label": "N = 22 (2 × 11)",
        "kind": "factor_of_2",
        "reason": (
            "Even N is out of scope: one division by 2 factors it classically, and Shor's "
            "reduction assumes an odd modulus."
        ),
    },
    {
        "n": 49,
        "label": "N = 49 (7 × 7)",
        "kind": "p_equals_q",
        "reason": (
            "p = q breaks the distinct-prime assumption: mod p² the only square roots of 1 are ±1, "
            "so the gcd step can never split N (and an integer square root factors it classically)."
        ),
    },
)
# Noisy attacks need gate-level circuits; only N = 15 transpiles quickly enough per request.
RSA_NOISE_MODULI: tuple[int, ...] = (15,)
RSA_MAX_NOISE_P = 0.2

# --------------------------------------------------------------------------------------
# Defence (protect -> re-attack -> compare) — owned by Defence Backend A.
# --------------------------------------------------------------------------------------

DEFENCE_METHODS: tuple[str, ...] = ("aes256", "mlkem", "bb84")
"""Exactly three defences: AES-256-GCM, ML-KEM-768 + AES-256-GCM, BB84 QKD + AES-256-GCM."""

MAX_DEFENCE_TEXT_CHARS = MAX_AES_TEXT_CHARS
"""Protect takes the organization's message up to the symmetric text limit."""

DEFENCE_REQUEST_TIMEOUT_S: float = float(os.getenv("QBREAK_DEFENCE_TIMEOUT_S", "60"))

BB84_DEFAULT_RAW_QUBITS = 1024
"""About 512 sifted bits, 384 after the QBER sample: enough for a 256-bit key on a clean channel."""
BB84_MIN_RAW_QUBITS = 128
BB84_MAX_RAW_QUBITS: int = int(os.getenv("QBREAK_BB84_MAX_RAW_QUBITS", "4096"))
BB84_BATCH_QUBITS = 64
"""Photons per circuit: each photon is an independent qubit, so circuits stay narrow."""
BB84_QBER_THRESHOLD = 0.11
BB84_MIN_QBER_THRESHOLD = 0.01
BB84_MAX_QBER_THRESHOLD = 0.25
BB84_MAX_CHANNEL_NOISE = 0.25
"""channel_noise is the per-photon bit-flip probability; 0.25 already guarantees an abort."""
BB84_SAMPLE_FRACTION = 0.25
"""Share of sifted bits disclosed publicly to estimate the QBER (then discarded)."""
BB84_PREVIEW_PHOTONS = 16
