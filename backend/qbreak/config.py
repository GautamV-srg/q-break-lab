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


ENABLED_KEY_BITS: list[int] = _integer_list("QBREAK_KEY_BITS", "4")
MAX_SHOTS = 4096
MAX_AES_TEXT_CHARS = 200


# ---------------------------------------------------------------------------
# RSA / public-key breach test (owned by the public-key backend; keep
# symmetric settings above this block so the two sides never collide)
# ---------------------------------------------------------------------------

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
